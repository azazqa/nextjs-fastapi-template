# shadcn/ui v4 전면 재설정 검증 — `chore/shadcn-v4-reset`

> 작성일: 2026-09-04
> 대상: `azazqa/nextjs-fastapi-template` — `chore/shadcn-v4-reset` @ `1bd772b` ("update frontend framework")
> 기준: `main` @ `f9a7363`
> 실행된 명령: `pnpm dlx shadcn@latest init --template next --base radix --preset b0 --force --reinstall --pointer`

---

## 검증 방법

추론이 아니라 실제 실행으로 확인했다.

```bash
git worktree add <tmp> origin/chore/shadcn-v4-reset
cd nextjs-frontend
pnpm install --no-frozen-lockfile      # 28.4s, 정상 완료
npx tsc --noEmit -p tsconfig.json      # → 5 errors
npx next build --webpack               # → 컴파일 실패
```

이후 아래 3건을 적용하고 재실행하여 **`tsc` 0 errors / `next build --webpack` 성공**을 확인했다.

> 빌드 검증 시 `next/font/google`이 `fonts.googleapis.com`을 받아오지 못해 폰트만 스텁으로 대체했다. 검증 환경의 네트워크 제한이며 저장소 문제가 아니다.

---

## 요약

| 구분 | 건수 | 상태 |
|---|---|---|
| **빌드 실패** | 3건 (tsc 오류 5개) | **수정 필요** |
| **미완 작업** | 폰트 1건 | **수정 필요** |
| 정상 동작 확인 | 6건 | 조치 불필요 |
| 남은 결정 | 4건 | 판단 필요 |

변경 규모: 38개 파일, +4555 / −2348. `components/ui/` 33개 중 32개 재생성, `forwardRef` 잔존 **0개**, `data-slot` 채택 **30개**.

---

# 1. 빌드 실패 — 3건

## F1. `lib/utils.ts`가 덮어써져 헬퍼 2개가 소실됐다

**가장 중요한 건이다.**

프리셋의 `registryDependencies`에 `utils`가 포함되어 있어, init이 이 파일을 `cn()`만 있는 표준 파일로 **교체**했다. 프로젝트 고유 헬퍼가 함께 사라졌다.

```
components/actions/login-action.ts(10,10):
  error TS2305: Module '"@/lib/utils"' has no exported member 'getErrorMessage'.
components/actions/password-reset-action.ts(6,10):
  error TS2305: Module '"@/lib/utils"' has no exported member 'getErrorMessage'.
```

소실된 것:

| 함수 | 호출처 | 조치 |
|---|---|---|
| `getErrorMessage()` | `login-action.ts` 1곳, `password-reset-action.ts` 2곳 | **복원 필수** |
| `makeClientId()` | 없음 (`main`에서도 미사용) | 복원 또는 폐기 — 판단 |

### 조치

```bash
git show main:nextjs-frontend/lib/utils.ts
```

에서 아래를 현재 `lib/utils.ts`에 되붙인다. 상단 `import type { ... } from "@/app/clientService";` 블록도 함께 필요하다.

```ts
import type {
  AuthJwtLoginError,
  ResetForgotPasswordError,
  ResetResetPasswordError,
} from "@/app/clientService";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

type ClientApiError =
  | AuthJwtLoginError
  | ResetForgotPasswordError
  | ResetResetPasswordError;

export function getErrorMessage(error: ClientApiError): string {
  let errorMessage = "An unknown error occurred";

  const detail = error.detail;
  if (typeof detail === "string") {
    errorMessage = detail;
  } else if (Array.isArray(detail) && detail.length > 0) {
    const parts = detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String(d.msg) : ""))
      .filter(Boolean);
    if (parts.length > 0) {
      errorMessage = parts.join("; ");
    }
  } else if (typeof detail === "object" && detail !== null && "reason" in detail) {
    errorMessage = String((detail as { reason: string }).reason);
  }

  return errorMessage;
}
```

### 재발 방지

`lib/utils.ts`는 shadcn이 소유권을 주장하는 파일이다. 앞으로 프로젝트 고유 헬퍼는 이 파일이 아니라 `lib/errors.ts` 같은 별도 모듈에 두는 편이 낫다. init이나 `add --overwrite`를 다시 돌릴 때마다 같은 일이 반복된다.

---

## F2. `components/ui/form.tsx`가 재생성되지 않고 legacy 상태로 남았다

```
components/ui/form.tsx(4,33): error TS2307: Cannot find module '@radix-ui/react-label'
components/ui/form.tsx(5,22): error TS2307: Cannot find module '@radix-ui/react-slot'
```

### 원인

`--reinstall`은 `components/ui/`의 파일명을 읽어 **레지스트리 인덱스에 존재하는 이름만** 재설치한다. 현재 shadcn 레지스트리에 `form`이 없다 — `field.tsx`가 그 역할을 대체했다. 따라서 이 파일 하나만 재생성 대상에서 빠져 구버전(`forwardRef` + 개별 `@radix-ui/*`)으로 남았고, 그 사이 `package.json`에서 해당 패키지들이 제거되면서 참조가 끊겼다.

### 조치 — 삭제

이 파일은 **저장소 어디에서도 import되지 않는다**(`grep` 확인). 되살릴 이유가 없다.

```bash
git rm nextjs-frontend/components/ui/form.tsx
```

폼 구성이 필요해지면 새로 생성된 `field.tsx`를 쓴다.

---

## F3. `components/page-pagination.tsx` — 제거된 아이콘 패키지 참조

```
components/page-pagination.tsx(13,59):
  error TS2307: Cannot find module '@radix-ui/react-icons'
```

`breadcrumb.tsx`와 `select.tsx`도 이전에는 이 패키지를 썼으나 재생성되며 lucide로 전환됐다. 커스텀 컴포넌트인 `page-pagination.tsx`만 남았다.

### 조치

```diff
- import { DoubleArrowLeftIcon, DoubleArrowRightIcon } from "@radix-ui/react-icons";
+ import { ChevronsLeft, ChevronsRight } from "lucide-react";
```

사용처의 컴포넌트 이름도 함께 바꾼다. 프리셋의 `iconLibrary`가 `lucide`이므로 이쪽으로 통일하는 것이 맞다.

---

# 2. 미완 작업 — 폰트

## F4. 한국어 서비스인데 본문 폰트가 Inter다

프리셋 `b0`의 `font` 값이 `inter`이고, 이것이 `registryDependencies: ["font-inter"]`로 들어와 `app/layout.tsx`를 ts-morph로 파싱해 코드를 주입했다.

### 현재 상태

```tsx
import { Noto_Sans_KR, Inter } from "next/font/google";   // ← Noto_Sans_KR 미사용
import { cn } from "@/lib/utils";

const inter = Inter({subsets:['latin'],variable:'--font-sans'});

<html lang="en" className={cn("font-sans", inter.variable)}>
  <body className={`${inter.variable}`}>
```

문제 4가지.

1. `Noto_Sans_KR` import만 남고 실제로는 Inter가 `--font-sans`를 차지했다
2. `display: "swap"`과 `weight` 지정이 사라졌다
3. `inter.variable`이 `<html>`과 `<body>` 양쪽에 중복으로 붙었다 — `<body>` 쪽은 불필요
4. `<html lang="en">` 그대로 — 한국어 콘텐츠다

### 조치

```tsx
import { Noto_Sans_KR } from "next/font/google";
import { cn } from "@/lib/utils";

const notoSansKR = Noto_Sans_KR({
  subsets: ["latin"],
  weight: ["100", "200", "300", "400", "500", "700", "900"],
  variable: "--font-sans",
  display: "swap",
});

// ...
<html lang="ko" className={cn("font-sans", notoSansKR.variable)}>
  <body>
```

> `subsets: ["latin"]`은 그대로 두어도 된다. Next.js 공식 문서 기준 `subsets`는 **preload 대상**을 정하는 값이지 제공되는 글리프를 자르는 값이 아니다.

### 부수 효과 — 기존 버그가 해소됐다

`variable: "--font-sans"`는 **그대로 유지**해야 한다. 새 `globals.css`가 이렇게 되어 있기 때문이다.

```css
@theme inline {
    --font-heading: var(--font-sans);
    --font-sans: var(--font-sans);
    ...
}
```

기존에는 `layout.tsx`가 `--font-sans`를 선언하는데 `globals.css`는 `--font-noto-sans-kr`을 참조하던 불일치가 있었다. 이번 재설정으로 양쪽이 `--font-sans`로 맞춰졌다.

---

# 3. 정상 확인 — 조치 불필요

## N1. `shadcn: "^4.20.1"`가 `dependencies`에 있는 것은 정상이다

CLI가 실수로 들어간 것이 아니다. 새 `globals.css` 3행이 이 패키지의 CSS를 실제로 import한다.

```css
@import "tailwindcss";
@import "tw-animate-css";
@import "shadcn/tailwind.css";     /* ← 이것 */
```

`shadcn` 패키지의 `exports`에 `"./tailwind.css": "./dist/tailwind.css"`가 선언되어 있고, 그 파일은 629줄로 accordion keyframes와 `data-open` 등 커스텀 variant를 담고 있다.

빌드 타임 의존이므로 `devDependencies`로 옮겨도 동작한다. 다만 Docker 빌드에서 `pnpm install --prod` 후 `next build`를 하는 구조라면 그대로 `dependencies`에 두는 편이 안전하다.

## N2. `combobox.tsx`의 `@base-ui/react`

정상이다. shadcn의 combobox는 `--base radix`에서도 Base UI 기반이다. `@base-ui/react`는 `package.json`에 그대로 남아 있다.

## N3. 커스텀 컴포넌트 무손상

`FormError.tsx`, `submitButton.tsx` — 레지스트리에 없는 이름이라 `--reinstall` 대상에서 필터링됐다. 예상대로 손상 없음.

## N4. Radix 패키지 통합

개별 `@radix-ui/react-*` 14개 제거, 통합 `radix-ui@^1.6.7` 추가. 정상.
(`@radix-ui/react-icons`는 F3 처리 후 제거 완료 상태로 유지)

## N5. `globals.css` 형태

정식 Tailwind v4 구조로 재작성됐다.

- `@theme inline`이 `hsl(var(--x))` 래퍼 없이 `var(--x)` 직접 참조
- `:root` / `.dark` 값이 oklch 완전 색상값
- `--radius-sm` ~ `--radius-4xl` calc 체계 생성
- `--pointer` 반영: `button:not(:disabled) { cursor: pointer }`
- 기존 `@plugin "tailwindcss-animate"` 잔재 없음 (사전 정리 효과)

## N6. 컴포넌트 세대 전환

| 항목 | 이전 | 현재 |
|---|---|---|
| `forwardRef` 사용 파일 | 22개 | **0개** |
| `data-slot` 사용 파일 | 4개 | **30개** |
| `components/ui/` 총 파일 | 34개 | 33개 (`form.tsx` 삭제 후) |
| `toggle-group.tsx`의 `bg-indigo-100` | 존재 | 제거됨 |

`components.json`도 `style: "new-york"` → `"radix-nova"`, `iconLibrary: "lucide"`, `menuColor`/`menuAccent`/`rtl` 추가로 갱신됐다.

---

# 4. 남은 결정 사항

## D1. `html { font-size: 12px }`

새 `globals.css`에서 사라졌다. 되살릴지 결정이 필요하다.

**되살리지 않는 쪽을 권한다.** Tailwind v4의 `--spacing`과 `--text-*` 네임스페이스로 밀도를 조절하는 편이 의도가 드러나고 서비스별 테마 레이어와도 맞물린다. root font-size를 줄이는 것은 모든 rem 값에 일괄로 걸리는 무딘 수단이다.

## D2. 하드코딩 색상 76곳

`app/` 69곳, `components/`(ui 제외) 7곳. 토큰으로 옮기는 작업은 그대로 남아 있다. 서비스별 테마 레이어 도입과 함께 처리하면 된다.

## D3. 다크 모드 활성화 경로 없음

`.dark` 블록은 생성됐고 `next-themes`도 설치되어 있으나, `layout.tsx`에 ThemeProvider가 없어 `.dark` 클래스가 붙을 방법이 없다. 기존부터의 상태이며 이번 작업과 무관하다. 관리자 화면에 다크 모드가 필요한지 먼저 정할 것.

## D4. Turbopack 마이그레이션

`next.config.mjs`가 `fork-ts-checker-webpack-plugin`을 위한 `webpack` 설정을 갖고 있는데 Next 16은 Turbopack이 기본이다. `next build`를 그냥 실행하면 실패한다.

```
⨯ ERROR: This build is using Turbopack, with a `webpack` config and no `turbopack` config.
```

현재는 `package.json`의 `dev`/`build` 스크립트가 `--webpack`을 명시하고 있어 문제가 드러나지 않는다. 기존 이슈이며 별도 과제로 다루면 된다.

---

# 적용 체크리스트

> 상태: **F1~F4 적용 완료** (2026-09-04)

- [x] **F1** `lib/errors.ts`에 `getErrorMessage()` 분리 (`makeClientId` 폐기, `utils.ts`는 `cn`만 유지)
- [x] **F2** `components/ui/form.tsx` 삭제
- [x] **F3** `page-pagination.tsx` — `@radix-ui/react-icons` → `lucide-react`
- [x] **F4** `layout.tsx` — Inter → Noto Sans KR, `lang="ko"`, `<body>` 중복 variable 제거
- [x] `npx tsc --noEmit` → 0 errors
- [x] `pnpm build` (`next build --webpack`) 성공
- [ ] 관리자 화면 육안 확인 — `new-york` → `radix-nova` 전환으로 버튼 variant/size 클래스 문자열이 달라졌다
- [x] D1 `font-size: 12px` 결정 — **되살리지 않음**
- [ ] (후속) 하드코딩 색상 76곳 → 토큰
- [ ] (후속) 서비스별 테마 레이어 `theme/tokens.css` 도입

---

## 관련 문서

- `theme-system-design-v2.md` — Tailwind v4 네임스페이스 기반 서비스별 테마 설계
- `frontend-cookie-followup.md` — N6·N7·N8 (적용 완료)
- `template-review.md` — 전체 검토 결과
