# 팔레트 적용 검증 — `1e43734`

> 작성일: 2026-09-04
> 대상: `azazqa/nextjs-fastapi-template` — `chore/shadcn-v4-reset` @ `1e43734` ("update 프론트엔드 색상 하드코딩 제거")
> 비교 기준: `cca3391` + 제안본
> 결과: **결함 1건**, 차트 팔레트 재조정 권고, 제안 외 변경 3건 확인

---

## 검증 방법

값을 재조정하셨기 때문에 제안본과의 일치 여부가 아니라 **적용본의 실제 값으로 처음부터 다시 계산**했다.

```bash
git fetch && git checkout 1e43734
pnpm install --no-frozen-lockfile
npx tsc --noEmit                                   # 0 errors
npx next build                                     # 성공 (Turbopack, 12 routes)
npx @tailwindcss/cli -i app/globals.css -o out.css # 유틸리티 생성 확인
```

대비는 `palette.css`를 파싱해 oklch → sRGB → WCAG 상대휘도로 직접 계산했다. 차트 색은 대비비 외에 **OKLab ΔE**를 함께 계산했다(이유는 5장).

---

## 1. 통과 항목

| 항목 | 결과 |
|---|---|
| 토큰 이름 일치 | `base.css` 55개 / `:root` 47개 / `.dark` 46개 — **누락·추가 0** |
| `tsc --noEmit` | 0 errors |
| `next build` | 성공 (Turbopack 기본 경로) |
| 하드코딩 색상 | **0곳** (shadcn 자체 `bg-black/50` 오버레이 2개 제외) |
| 컴파일된 CSS의 팔레트 유틸리티 | `gray-*` · `blue-*` · `indigo-*` 등 **0개** |
| 신설 유틸리티 | `bg-success-soft`, `text-warning-soft-foreground` 등 전부 생성 |
| 텍스트 대비 (40개 조합) | **39개 통과 / 1개 미달** |

재조정한 값 중 제안본보다 나아진 것도 있다.

- `--foreground`를 `0.2538`로 올려 순수 검정에서 벗어남 — 장시간 열어두는 관리 화면에 적합
- light `--destructive`를 `0.5054`로 낮춰 흰 글자 대비 6.20 확보 (제안본 4.54)

---

## 2. 결함 — 다크 모드 `--destructive-foreground`

```css
.dark {
  --destructive: oklch(0.65 0.18 22);            /* #E8575B */
  --destructive-foreground: oklch(0.985 0 0);    /* 흰색 */
}
```

**대비 3.38 — WCAG AA(4.5) 미달.**

### 원인

light에서는 `--destructive`가 `0.5054`(어두운 빨강)이라 흰 글자가 6.20으로 통과한다. dark에서 배경 빨강을 `0.65`로 **밝히면서 foreground는 흰색 그대로** 두었다. 두 값은 반대 방향으로 움직여야 한다.

### 조치 — 둘 중 하나

```css
/* A. foreground 를 어둡게 — 배경색 유지 (권장) */
--destructive-foreground: oklch(0.20 0.04 22);   /* 5.18 ✔ */

/* B. 배경을 어둡게 — 흰 글자 유지 */
--destructive: oklch(0.55 0.18 22);              /* 5.31 ✔ */
```

**A를 권한다.** dark에서 `--destructive`는 글자 배경만이 아니라 아이콘·테두리·강조선으로도 쓰인다. B는 그 밝기를 낮춰 어두운 배경에서 눈에 덜 띄게 만든다.

참고로 `--destructive-foreground` 값별 대비는 다음과 같다.

| `--destructive-foreground` | 현재 `--destructive` 위 대비 |
|---|---|
| `oklch(0.18 0.04 22)` | 5.38 |
| `oklch(0.20 0.04 22)` | 5.18 |
| `oklch(0.22 0.05 22)` | 4.96 |
| `oklch(0.25 0.04 22)` | 4.58 |
| `oklch(0.985 0 0)` — 현재 | **3.38** |

### 긴급도 — 낮음

현재 `--destructive-foreground`를 참조하는 코드가 없다. nova 스타일의 destructive 버튼은 `text-white`를 직접 쓴다. **삭제 확인 다이얼로그나 오류 배너를 붙이는 시점**에 드러난다. 그전에 고쳐두면 된다.

---

## 3. 차트 팔레트 — 인접 두 색

### 먼저, 앞선 구두 답변의 정정

대화에서 차트 시리즈를 **대비비(contrast ratio)** 로 평가하며 "`chart-1`/`chart-5` 1.03 — 사실상 같은 색"이라고 말했다. **이 판단은 틀렸다.**

대비비는 **휘도 차이만** 측정한다. 명도가 같고 색상만 다른 두 색(파랑과 초록)은 대비비 1.0이지만 육안으로는 명확히 구분된다. 범주형(categorical) 색 팔레트의 구분성은 **OKLab 공간의 지각 거리 ΔE**로 봐야 한다.

다시 계산한 결과다.

### LIGHT

| 색 | hex | 배경대비 |
|---|---|---|
| `chart-1` | `#035AA6` | 6.96 |
| `chart-2` | `#049DD9` | 3.07 |
| `chart-3` | `#04B2D9` | 2.51 |
| `chart-4` | `#F2C438` | 1.65 |
| `chart-5` | `#198044` | 4.99 |

| 쌍 | ΔE | ΔL | ΔH |
|---|---|---|---|
| **`chart-2` / `chart-3`** | **0.060** | 0.050 | **13.8°** |
| `chart-1` / `chart-2` | 0.195 | 0.190 | 17.9° |
| `chart-1` / `chart-5` | 0.218 | 0.062 | 100.8° |
| 나머지 6쌍 | 0.219 ~ 0.473 | | |

### DARK

| 쌍 | ΔE | ΔL | ΔH |
|---|---|---|---|
| **`chart-1` / `chart-2`** | **0.060** | 0.050 | **13.8°** |
| `chart-1` / `chart-5` | 0.150 | 0.001 | 66.1° |
| 나머지 8쌍 | 0.189 ~ 0.473 | | |

### 결론

**진짜 문제는 한 쌍이다** — `#049DD9`와 `#04B2D9`. 명도 차이 0.05, 색상 차이 13.8°, ΔE 0.060. 원본 팔레트에 이미 인접한 두 색이 들어 있고 그것을 그대로 이웃 시리즈에 배치했다. 꺾은선 두 개를 눈으로 구분할 수 없다.

`chart-1`/`chart-5`(파랑 대 초록, ΔH 66~100°)는 **구분된다.** 대비비만 보고 판단했던 것을 정정한다. 다만 dark에서 ΔL이 0.001이라 **흑백 인쇄나 명도 위주 색각 조건에서는 겹친다** — 채워진 영역(막대·파이)에는 문제없고, 얇은 선에는 약하다.

### 배경 대비 미달 2건

- **dark `chart-3` = `#035AA6`, 대비 2.76** — 어두운 배경 위의 남색이라 실제로 잘 안 보인다
- **light `chart-4` = `#F2C438`, 대비 1.65** — 흰 배경 위의 금색. 채워진 면적에는 괜찮고, 1~2px 선이나 작은 점에는 부족하다

---

## 4. 차트 5색 재조정안

브랜드 색상을 유지하면서 **ΔE ≥ 0.15**와 배경 대비를 확보한 값이다.

```css
:root {
  --chart-1: oklch(0.4672 0.1416 252.82);   /* #035AA6  대비 6.96 */
  --chart-2: oklch(0.6570 0.1385 234.89);   /* #049DD9  대비 3.07 */
  --chart-3: oklch(0.5292 0.1294 152.07);   /* #198044  대비 4.99 */
  --chart-4: oklch(0.8383 0.1556  89.47);   /* #F2C438  대비 1.65 */
  --chart-5: oklch(0.6200 0.1600 300.00);   /* #966CD7  대비 3.87 */
}

.dark {
  --chart-1: oklch(0.7072 0.1292 221.05);   /* #04B2D9  대비  7.67 */
  --chart-2: oklch(0.5800 0.1450 253.00);   /* #307CCD  대비  4.48 */
  --chart-3: oklch(0.7087 0.1447 154.91);   /* #45BB78  대비  7.91 */
  --chart-4: oklch(0.8383 0.1556  89.47);   /* #F2C438  대비 11.66 */
  --chart-5: oklch(0.7200 0.1500 300.00);   /* #B48DF4  대비  7.38 */
}
```

| | 현재 최소 ΔE | 조정 후 최소 ΔE | 현재 최소 배경대비 | 조정 후 |
|---|---|---|---|---|
| light | 0.060 | **0.166** | 1.65 | 1.65 |
| dark | 0.060 | **0.149** | 2.76 | **4.48** |

### 무엇을 바꿨나

1. **`#04B2D9`를 차트에서 뺐다.** `#049DD9`와 너무 가깝다. 이 색은 dark `--primary`·`--info`로 이미 쓰이고 있으니 정체성은 유지된다
2. **초록을 3번으로 올리고 5번에 보라(`H 300`)를 넣었다.** 원본 팔레트는 파랑 계열 3색 + 금색이라 5개 시리즈를 채울 색상 폭이 없다. 다섯 번째는 팔레트 밖에서 가져와야 한다
3. **dark의 남색(`#035AA6`)을 초록으로 교체했다.** 배경 대비 2.76 → 7.91

### 남은 한계

**light `chart-4`(금색)의 배경 대비 1.65는 해결하지 못한다.** `#F2C438`은 흰 배경에서 본질적으로 밝다. 3.0을 맞추려면 `L`을 0.62 근처까지 내려야 하는데 그러면 올리브색이 되어 브랜드 색이 아니게 된다.

실무적 처리는 두 가지다.

- **채워진 면적(막대·영역·파이)에만 쓴다** — 면적이 넓으면 1.65로도 인지에 문제없다
- **꺾은선에 쓸 때는 선 굵기를 3px 이상**으로 하거나 어두운 테두리를 넣는다

shadcn의 기본 차트 팔레트(nova)도 흰 배경 대비 1.2 수준의 회색조라, 이 지점은 업계 관행상 엄격히 지켜지지 않는 영역이다.

### 적용 시점

**지금 당장은 필요 없다.** `chart-*` 토큰을 참조하는 코드가 아직 없고 `echarts`도 미사용이다. 첫 차트를 붙일 때 함께 반영하면 된다.

---

## 5. 왜 대비비가 아니라 ΔE인가

| 지표 | 측정하는 것 | 적합한 용도 |
|---|---|---|
| WCAG 대비비 | 휘도(luminance) 비율 | 글자 ↔ 배경, UI 요소 ↔ 배경 |
| OKLab ΔE | 명도 + 색상 + 채도의 지각 거리 | **범주형 색 간 구분성** |

파랑 `#035AA6`(L 0.467)과 초록 `#198044`(L 0.529)은 대비비 1.40이다. 이 숫자만 보면 "구분 안 됨"이지만, 두 색은 색상이 100° 떨어져 있어 누구나 구분한다. 반대로 `#049DD9`와 `#04B2D9`는 대비비 1.23으로 비슷해 보이지만 색상 차이가 13.8°뿐이라 **정말로** 구분되지 않는다.

같은 대비비 숫자가 정반대 결론을 가리킨다. 차트 시리즈 색을 고를 때는 ΔE를 보고, 글자와 배경을 고를 때는 대비비를 본다.

### 색각 이상 관점

현재 팔레트에 빨강 계열 시리즈가 없어 적록색각이상(가장 흔한 유형)에서 위험한 조합은 없다. 재조정안의 보라(`H 300`)도 파랑·초록과 충분히 떨어진다.

---

## 6. 제안 외 변경 3건

### 6-1. Turbopack 전환 — 확인

```diff
- import ForkTsCheckerWebpackPlugin from 'fork-ts-checker-webpack-plugin';
  const nextConfig = {
-   webpack: (config, { isServer }) => { ... },
    transpilePackages: ['echarts', 'zrender'],
  };
```
```diff
- "dev": "next dev --webpack",
- "build": "next build --webpack",
+ "dev": "next dev",
+ "build": "next build",
```

앞선 문서의 **D4가 해소됐다.** 기본 `next build`(Turbopack)로 빌드 성공을 확인했다.

**다만 dev 중 전역 타입 검사가 사라졌다.** `fork-ts-checker-webpack-plugin`이 하던 일이다. `next build`는 자체적으로 `tsc`를 돌리므로 빌드 타임 안전성은 유지되지만, 개발 중에는 편집기와 `pnpm lint`에 의존하게 된다.

**CI에 한 줄 넣어두는 것을 권한다.**

```yaml
- run: npx tsc --noEmit
```

### 6-2. `sidebar.tsx`에 `TooltipProvider` 추가 — 필요한 수정

```diff
  <SidebarContext.Provider value={contextValue}>
+   <TooltipProvider delayDuration={0}>
      <div data-slot="sidebar-wrapper" ...>
        {children}
      </div>
+   </TooltipProvider>
  </SidebarContext.Provider>
```

새 `tooltip.tsx`의 `Tooltip`은 `TooltipPrimitive.Root` 그대로다. Provider 조상이 없으면 Radix가 예외를 던진다. **필요한 수정이 맞다.**

**다만 `sidebar.tsx`는 shadcn 소유 파일이라 다음 재생성 때 사라진다.** `app/layout.tsx`에서 앱 전체를 감싸는 편이 낫다.

```tsx
// app/layout.tsx
<body>
  <TooltipProvider delayDuration={0}>
    <NextTopLoader color="var(--primary)" height={3} showSpinner={false} />
    {children}
    <Toaster richColors />
  </TooltipProvider>
</body>
```

재생성에 영향받지 않고, 사이드바 밖의 툴팁도 함께 해결된다.

### 6-3. `--chart-5` = 성공 초록 — 확인 필요

light `#198044`, dark `#45BB78`로 `--success`와 **같은 값**이다. 의도한 것이라면 그대로 두어도 되지만, 차트에서 초록이 "성공/정상"으로 읽힐 여지가 있다. 4장 재조정안에서는 초록을 `chart-3`으로 옮기고 5번에 보라를 넣었다.

---

# 체크리스트

> 상태: **즉시 조치 적용 완료** (2026-09-04). 차트·ThemeProvider는 후속.

- [x] **`.dark --destructive-foreground`** → `oklch(0.20 0.04 22)` (결함, 2장)
- [x] `TooltipProvider`를 `app/layout.tsx`로 이동 (6-2)
- [x] 타입체크 게이트 — `make typecheck-frontend` (`pnpm run tsc`)
- [ ] (차트 도입 시) `--chart-1` ~ `--chart-5` 재조정 (4장)
- [ ] (선택) ThemeProvider 연결 후 다크 모드 육안 확인

---

## 관련 문서

- `theme-palette-setup.md` — 테마 레이어 구성 · 팔레트 설계
- `shadcn-v4-reset-review.md` — F1~F4 검증
