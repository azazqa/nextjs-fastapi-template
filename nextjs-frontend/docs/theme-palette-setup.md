# 컬러 팔레트 · 테마 레이어 구성

> 작성일: 2026-09-04
> 대상: `azazqa/nextjs-fastapi-template` — `chore/shadcn-v4-reset` @ `cca3391` 기준
> 출처 팔레트: Adobe Color — `#035AA6` `#049DD9` `#04B2D9` `#F2C438` `#F2F2F2`
> 결과: 하드코딩 색상 **82곳 → 0곳**, WCAG AA 전 조합 통과, `tsc` 0 errors / `next build` 성공

---

## 0. 선행 확인

F1~F4 적용 상태를 먼저 검증했다. 네 건 모두 반영되어 있고 `tsc --noEmit`은 0 errors다.

`getErrorMessage()`를 `lib/utils.ts`가 아니라 **`lib/errors.ts`로 분리**한 것은 좋은 선택이다. `lib/utils.ts`는 shadcn이 소유권을 주장하는 파일이라, 앞으로 CLI를 다시 돌려도 프로젝트 헬퍼가 날아가지 않는다.

---

## 1. 팔레트 역할 배정

원본 5색을 그대로 토큰에 넣지 않았다. shadcn 토큰은 **역할(role)** 이고, 각 역할에는 대비 요구치가 붙어 있기 때문이다.

| 원본 | oklch | 배정된 역할 | 근거 |
|---|---|---|---|
| `#035AA6` | `oklch(0.4672 0.1416 252.82)` | **light `--primary`**, `--chart-1`, `--sidebar-primary` | 흰 글자 대비 6.96 — 버튼 배경으로 안전 |
| `#049DD9` | `oklch(0.6570 0.1385 234.89)` | **`--ring`**(양쪽), light `--info`, `--chart-2` | 흰 배경 대비 3.07 — 포커스 링 기준(3:1) 충족. **본문 글자색으로는 부적합** |
| `#04B2D9` | `oklch(0.7072 0.1292 221.05)` | **dark `--primary`**, dark `--info`, `--chart-3` | 어두운 배경 위에서 대비 7.62 |
| `#F2C438` | `oklch(0.8383 0.1556 89.47)` | **`--warning`**(양쪽), `--chart-4` | 검은 글자 대비 12.73 |
| `#F2F2F2` | `oklch(0.9612 0.0000 89.88)` | **`--muted` / `--secondary` 계열**의 기준 명도 | 253° 색상을 아주 약하게 섞어 브랜드와 같은 계열로 통일 |

### 주의했던 지점

**`#049DD9`를 링크 색으로 쓰지 않았다.** 흰 배경 대비가 3.07이라 본문 텍스트 AA(4.5)에 미달한다. 기존 코드의 `text-blue-500`은 전부 `text-primary`(`#035AA6`, 6.96)로 갔다.

**`--accent`는 브랜드 강조색이 아니다.** shadcn에서 `--accent`/`--accent-foreground`는 **메뉴·리스트의 hover 배경**이다. 여기에 채도 높은 브랜드 색을 넣으면 드롭다운 전체가 파랗게 물든다. 그래서 아주 옅은 파랑 틴트(`#EBF1F8`)로 잡았다.

**중립색에 253° 색상을 미세하게 넣었다.** 순수 회색 대신 `chroma 0.004~0.032` 수준의 파랑 기미를 넣어 브랜드 블루와 같은 계열로 읽히게 했다. 육안으로는 회색이지만 화면 전체 톤이 정돈된다.

---

## 2. 파일 구조

```
app/globals.css          ← 엔트리. import 만.
app/theme/base.css       ← 구조: 어떤 토큰이 존재하는가   (프레임워크 고정)
app/theme/palette.css    ← 값: 그 토큰이 무슨 색인가      ★ 서비스별 교체 지점
```

`app/globals.css` 전문:

```css
@import "tailwindcss";
@import "tw-animate-css";
@import "shadcn/tailwind.css";
@import "./theme/base.css";
@import "./theme/palette.css";

/* docs/*.md 안의 예시 클래스가 유틸리티로 생성되는 것을 막는다 */
@source not "../docs";
```

### 왜 둘로 나눴나

`@theme inline`의 `--color-*` 매핑과 `@layer base`는 **한 번 정하면 서비스마다 바뀌지 않는다.** 반대로 `:root`/`.dark`의 값은 서비스마다 전부 바뀐다. 섞어두면 새 서비스를 팔 때 "어디까지 복사해야 하는지"를 매번 판단해야 한다.

나눠두면 **서비스 하나 = `palette.css` 파일 하나**로 끝난다.

### `@source not "../docs"` 를 넣은 이유

빌드 산출물을 뜯어보니 `.bg-indigo-100` 유틸리티가 남아 있었다. 출처는 `docs/shadcn-v4-reset-review.md` — 저장소에 커밋된 **검토 문서 안의 코드 예시**였다. Tailwind v4는 프로젝트 트리를 자동 스캔하므로 `.md` 파일 안의 클래스 문자열도 유틸리티로 만들어낸다.

이 한 줄로 CSS 출력이 정리됐고, 앞으로 문서에 색상 예시를 써도 번들에 새지 않는다.

> 경로 주의 — `@source`는 **CSS 파일 기준 상대경로**다. `app/globals.css`에서 `../docs`는 `nextjs-frontend/docs/`를 가리킨다(저장소 루트의 `docs/`가 아니다). 검토 문서가 실제로 그 위치에 있는 것을 확인하고 맞춘 값이므로, 문서를 옮기면 이 경로도 함께 고쳐야 한다.

---

## 3. 토큰 세트

기존 shadcn 토큰 전부 + **상태(status) 토큰 16개를 신설**했다.

### 신설 토큰

| 이름 | 용도 |
|---|---|
| `--success` / `--success-foreground` | 성공 상태 솔리드 |
| `--warning` / `--warning-foreground` | 경고 상태 솔리드 |
| `--info` / `--info-foreground` | 정보 상태 솔리드 |
| `--success-soft` / `--success-soft-foreground` | 배지·배너용 옅은 배경 + 진한 글자 |
| `--warning-soft` / `--warning-soft-foreground` | 〃 |
| `--info-soft` / `--info-soft-foreground` | 〃 |
| `--destructive-soft` / `--destructive-soft-foreground` | 〃 |

`bg-success-soft text-success-soft-foreground` 형태로 쓴다. **기존 `bg-green-100 text-green-900 dark:bg-green-950 dark:text-green-200` 네 개 클래스가 두 개로 줄고, `dark:` 변형이 사라진다** — 값이 토큰 안에서 이미 갈라지기 때문이다.

### 주요 값

| 토큰 | light | dark |
|---|---|---|
| `--primary` | `#035AA6` | `#04B2D9` |
| `--ring` | `#049DD9` | `#049DD9` |
| `--muted` | `#F0F2F5` | `#222A33` |
| `--border` | `#D9DEE5` | `#2C343D` |
| `--success` | `#198044` | `#45BB78` |
| `--warning` | `#F2C438` | `#F2C438` |
| `--info` | `#049DD9` | `#04B2D9` |

값은 전부 **oklch로만** 적었다. hex는 주석에만 둔다 — oklch는 명도(L)를 독립적으로 조절할 수 있어서, 다크 모드 변형을 만들 때 색상·채도를 유지한 채 L만 옮기면 된다.

---

## 4. 대비 검증

sRGB → OKLab 변환과 WCAG 상대휘도를 직접 계산해 전 조합을 확인했다. **미달 0건.**

| 조합 | light | dark | 기준 |
|---|---|---|---|
| `foreground` / `background` | 17.70 | 17.47 | 4.5 |
| `muted-foreground` / `background` | 5.51 | 7.72 | 4.5 |
| `muted-foreground` / `muted` | 4.92 | 5.87 | 4.5 |
| `primary-foreground` / `primary` | 6.66 | 7.46 | 4.5 |
| `secondary-foreground` / `secondary` | 11.42 | 13.30 | 4.5 |
| `accent-foreground` / `accent` | 10.93 | 11.95 | 4.5 |
| `destructive-foreground` / `destructive` | 4.54 | 6.58 | 4.5 |
| `success-foreground` / `success` | 4.78 | 7.81 | 4.5 |
| `warning-foreground` / `warning` | 8.83 | 9.96 | 4.5 |
| `info-foreground` / `info` | 5.85 | 7.44 | 4.5 |
| `success-soft-foreground` / `success-soft` | 9.02 | 10.09 | 4.5 |
| `warning-soft-foreground` / `warning-soft` | 8.09 | 9.89 | 4.5 |
| `info-soft-foreground` / `info-soft` | 8.36 | 9.56 | 4.5 |
| `destructive-soft-foreground` / `destructive-soft` | 8.08 | 9.07 | 4.5 |

| UI 요소 대비 | light | dark | 기준 |
|---|---|---|---|
| `primary` / `background` | 6.96 | 7.62 | 3.0 |
| `ring` / `background` | 3.07 | 6.21 | 3.0 |

> `success`는 초기값 `oklch(0.56 …)`에서 4.23으로 미달이 나왔다. `L`을 0.53으로 내려 4.78을 확보했다. 나머지는 첫 설계값 그대로 통과했다.

---

## 5. 하드코딩 색상 치환 — 82곳

| 파일 | 건수 | 주요 치환 |
|---|---|---|
| `app/(public)/login/page.tsx` | 24 | 아래 상세 |
| `app/(protected)/admin/scheduler/page.tsx` | 22 | StatusBadge → soft 토큰, `bg-white dark:bg-gray-900` → `bg-card` |
| `app/(public)/password-recovery/page.tsx` | 21 | login과 동일 패턴 |
| `components/ui/FormError.tsx` | 3 | `text-red-500` → `text-destructive` |
| `app/(protected)/layout.tsx` | 2 | `border-indigo-700` → `border-primary`, `bg-gray-100` → `bg-muted` |
| `app/(public)/password-recovery/confirm/page.tsx` | 2 | `text-red-500` → `text-destructive` |
| `components/page-pagination.tsx` | 1 | `text-gray-600` → `text-muted-foreground` |
| `components/page-size-selector.tsx` | 1 | 〃 |
| `components/user-menu.tsx` | 1 | `border border-gray-600` → `border` |
| `app/(protected)/page.tsx` | 1 | `text-gray-600` → `text-muted-foreground` |
| `app/layout.tsx` | 1 | `NextTopLoader color="#2563eb"` → `"var(--primary)"` |

### 치환이 아니라 **삭제**한 것들

로그인/비밀번호 화면의 상당수는 대응 토큰으로 바꾸는 대신 **클래스를 지웠다.** shadcn 컴포넌트가 이미 올바른 기본값을 갖고 있어서 덧칠이었을 뿐이다.

```diff
- <Card className="w-full max-w-sm rounded-lg shadow-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800">
+ <Card className="w-full max-w-sm rounded-lg shadow-lg">
```
`Card`는 이미 `bg-card border`를 갖는다.

```diff
- <CardDescription className="text-sm text-gray-600 dark:text-gray-400">
+ <CardDescription className="text-sm">
```
`CardDescription`은 이미 `text-muted-foreground`다.

```diff
- <Label htmlFor="username" className="text-gray-700 dark:text-gray-300">
+ <Label htmlFor="username">

- <Input id="username" ... className="border-gray-300 dark:border-gray-600" />
+ <Input id="username" ... />
```

이게 근본 처방이다. 토큰으로 바꿔놓으면 다음에 shadcn 기본값이 바뀔 때 또 어긋난다.

### StatusBadge

```diff
- if (status === "PENDING")    cls = "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200";
- if (status === "PROCESSING") cls = "bg-blue-100 text-blue-900 dark:bg-blue-950 dark:text-blue-200";
- if (status === "SUCCEEDED")  cls = "bg-green-100 text-green-900 dark:bg-green-950 dark:text-green-200";
- if (status === "FAILED")     cls = "bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200";
- if (status === "CANCELLED")  cls = "bg-gray-200 text-gray-800 dark:bg-gray-800 dark:text-gray-200";
+ if (status === "PENDING")    cls = "bg-warning-soft text-warning-soft-foreground";
+ if (status === "PROCESSING") cls = "bg-info-soft text-info-soft-foreground";
+ if (status === "SUCCEEDED")  cls = "bg-success-soft text-success-soft-foreground";
+ if (status === "FAILED")     cls = "bg-destructive-soft text-destructive-soft-foreground";
+ if (status === "CANCELLED")  cls = "bg-secondary text-secondary-foreground";
```

### 링크

```diff
- className="ml-auto inline-block text-sm text-blue-500 hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-500"
+ className="ml-auto inline-block text-sm text-primary hover:text-primary/80"
```

### 남긴 것

`components/ui/dialog.tsx:42`와 `sheet.tsx:40`의 `bg-black/50`은 그대로 뒀다. shadcn이 배포하는 오버레이 코드이고, 다음 재생성 때 어차피 되돌아온다.

---

## 6. 검증

```bash
pnpm install
npx tsc --noEmit                # 0 errors
npx @tailwindcss/cli -i app/globals.css -o /tmp/out.css
npx next build --webpack        # 성공 (12 routes)
```

컴파일 산출물에서 확인한 것:

- `.bg-success-soft { background-color: var(--success-soft) }` 등 신설 유틸리티 **전부 생성됨**
- `.bg-primary\/15` 투명도 modifier → `color-mix(in oklab, …)` 정상
- `.rounded-sm { border-radius: calc(var(--radius) * 0.6) }` — `--radius` 연동 정상
- `.dark\:*:is(.dark *)` 다크 변형 정상
- 팔레트 계열 유틸리티(`gray-*`, `blue-*`, `indigo-*` …) **잔존 0개**

> 빌드 검증 시 `next/font/google`이 검증 환경의 네트워크 제한으로 `fonts.googleapis.com`을 받지 못해 폰트만 스텁 처리했다. 저장소 문제가 아니다.

---

## 7. 새 서비스에 다른 팔레트 적용하기

`app/theme/palette.css` **하나만** 복사해서 값을 바꾼다. `base.css`와 `globals.css`는 손대지 않는다.

```
app/theme/
  base.css          ← 공통
  palette.css       ← 서비스 A (현재)
```

작업 순서:

1. 원본 색 3~5개를 정한다
2. 각각을 oklch로 변환한다 — `oklch.com` 또는 첨부한 `color.py`
3. **역할을 먼저 정하고**, 대비를 확인한 뒤 값을 넣는다
   - `primary` ↔ `primary-foreground` ≥ 4.5
   - `primary` ↔ `background` ≥ 3.0
   - `muted-foreground` ↔ `muted` ≥ 4.5
4. light와 dark를 **반드시 함께** 정의한다. 한쪽만 바꾸면 다른 모드에서 색이 어긋난다
5. 대비가 모자라면 **`L` 값만 조절한다.** 색상(H)과 채도(C)는 그대로 두어야 팔레트의 정체성이 유지된다

### 런타임 테마 전환이 필요해지면

지금 구조는 "빌드 시점에 팔레트 하나"다. 한 빌드에서 여러 테마를 전환해야 한다면 선택자에 속성을 더한다.

```css
:root[data-theme="ocean"]      { --primary: …; }
:root[data-theme="ocean"].dark { --primary: …; }
```

`:root[data-theme]`는 특정도 (0,2,0)으로 `:root`(0,1,0)를 이기므로 import 순서와 무관하게 동작한다. 다만 **그 테마 블록은 전체 토큰을 빠짐없이 정의해야 한다** — 일부만 덮으면 light 블록(0,2,0)이 `.dark`(0,1,0)를 이겨서 다크 모드가 깨진다.

---

## 8. 주의 사항

**향후 `shadcn add`가 CSS 변수를 들고 오면 `globals.css`에 쓴다.** `components.json`의 `tailwind.css`가 `app/globals.css`를 가리키기 때문이다. `registry:theme`·`registry:style`·`registry:base`·`registry:font` 타입 항목을 설치할 때만 발생하고, 일반 컴포넌트 추가(`shadcn add button`)에서는 일어나지 않는다. 만약 발생하면 추가된 `:root` 블록을 `palette.css`로 옮기면 된다.

**다크 모드는 여전히 활성화 경로가 없다.** `.dark` 값은 전부 준비됐고 `next-themes`도 설치돼 있지만 `layout.tsx`에 ThemeProvider가 없다. 관리자 화면에 다크 모드가 필요한지 먼저 정할 것.

---

## 9. 밀도(density) — `html { font-size: 12px }` 처리

**결론: 복원하지 않는다.** 재설정 과정에서 사라진 채로 둔다.

### 왜

`font-size: 12px`은 root font-size를 낮춰 **모든 rem 값을 한꺼번에** 줄인다. 여백·글자·아이콘·모서리 반경이 같은 비율로 따라 움직이므로 "표는 촘촘하게, 본문은 그대로" 같은 조정이 불가능하다. Tailwind v4에는 그 두 축이 분리된 토큰이 있다.

| 축 | 토큰 | 영향 범위 |
|---|---|---|
| 여백 | `--spacing` | `p-*`, `m-*`, `gap-*`, `space-*`, `size-*`, `w-*`, `h-*` |
| 글자 | `--text-*` | `text-xs` ~ `text-4xl` |

### 필요해지면 이렇게 한다

`palette.css`의 `:root`에 값만 추가한다. `base.css`나 컴포넌트는 건드리지 않는다.

```css
:root {
  /* 여백만 촘촘하게 — 기본 0.25rem */
  --spacing: 0.22rem;

  /* 글자만 작게 — 기본값 대비 한 단계 */
  --text-sm: 0.8125rem;
  --text-base: 0.875rem;
}
```

`p-4`는 `calc(var(--spacing) * 4)`로 컴파일되므로 `--spacing` 한 줄이 전체 여백 스케일을 옮긴다. 앞서 컴파일 검증에서 이 동작을 확인했다.

행 높이도 함께 조절하려면 `--text-*--line-height` 형태의 하위 토큰을 쓴다.

```css
:root {
  --text-sm: 0.8125rem;
  --text-sm--line-height: 1.4;
}
```

### 지금 넣지 않은 이유

기본값으로 한 번 보고 판단하는 편이 낫다. 미리 넣으면 "원래 이 크기가 맞는지"를 비교할 기준이 없어진다. 화면을 확인한 뒤 성기게 느껴지는 축만 골라 조절한다.

---

# 체크리스트

> 상태: **적용 완료** (2026-09-04) — D3 ThemeProvider는 보류

- [x] `app/theme/base.css` 추가
- [x] `app/theme/palette.css` 추가
- [x] `app/globals.css` 교체 (import + `@source not`)
- [x] 10개 파일 색상 치환 (첨부 patch)
- [x] `npx tsc --noEmit` → 0 errors
- [x] `pnpm build` 성공 (Turbopack)
- [ ] 로그인 · 비밀번호 재설정 · 스케줄러 화면 육안 확인
- [ ] (선택) ThemeProvider 연결 후 다크 모드 확인

> `html { font-size: 12px }` 복원 여부는 **복원하지 않음**으로 확정됐다 (9장 참조). 별도 조치 없음.

---

## 첨부

- `theme-base.css` — `app/theme/base.css`
- `theme-palette.css` — `app/theme/palette.css`
- `theme-globals.css` — `app/globals.css`
- `theme-palette.patch` — 전체 변경 (`git apply`)

## 관련 문서

- `shadcn-v4-reset-review.md` — F1~F4 검증
- `theme-system-design-v2.md` — Tailwind v4 네임스페이스 기반 테마 설계
