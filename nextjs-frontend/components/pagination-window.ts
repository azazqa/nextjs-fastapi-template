/** 현재 페이지 ±2 윈도우 + 양끝 페이지/ellipsis 목록 생성 (페이지네이션 공통) */
export function buildPageWindow(
  currentPage: number,
  totalPages: number,
): Array<number | "ellipsis"> {
  const max = Math.max(1, totalPages);
  const start = Math.max(1, currentPage - 2);
  const end = Math.min(max, currentPage + 2);

  const out: Array<number | "ellipsis"> = [];
  if (start > 1) {
    out.push(1);
    if (start > 2) out.push("ellipsis");
  }
  for (let p = start; p <= end; p += 1) out.push(p);
  if (end < max) {
    if (end < max - 1) out.push("ellipsis");
    out.push(max);
  }
  return out;
}
