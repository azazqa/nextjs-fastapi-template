const DISPLAY_TIMEZONE = "Asia/Seoul";

/**
 * API에서 오는 datetime 문자열을 파싱합니다.
 * - 끝에 Z / ±hh:mm 오프셋이 없으면 UTC로 간주하고 'Z'를 붙입니다.
 * - `YYYY-MM-DD HH:mm:ss` 형태(공백 구분)는 `T`로 바꿔 ISO로 맞춥니다.
 */
export function parseApiDateTime(iso: string | null | undefined): Date | null {
  if (iso == null || iso === "") return null;
  if (typeof iso === "number" && Number.isFinite(iso)) {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  if (typeof iso !== "string") return null;

  let trimmed = iso.trim();
  if (!trimmed) return null;

  // "YYYY-MM-DD HH:mm:ss..." → ISO 8601 (일부 환경에서 공백만으로는 Invalid Date)
  if (/^\d{4}-\d{2}-\d{2}\s+\d/.test(trimmed)) {
    trimmed = trimmed.replace(/^(\d{4}-\d{2}-\d{2})\s+/, "$1T");
  }

  // 끝이 Z 또는 ±오프셋 (소수 초 뒤 오프셋 포함: ...+09:00)
  const hasOffsetOrZ = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(trimmed);

  const candidate = hasOffsetOrZ ? trimmed : trimmed + "Z";
  let d = new Date(candidate);
  if (!Number.isNaN(d.getTime())) return d;

  d = new Date(trimmed);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDateInSeoul(iso: string | null | undefined): string {
  const d = parseApiDateTime(iso);
  if (!d) return "-";
  return d.toLocaleDateString("ko-KR", {
    timeZone: DISPLAY_TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

export function formatDateTimeInSeoul(iso: string | null | undefined): string {
  const d = parseApiDateTime(iso);
  if (!d) return "-";
  // NOTE:
  // - 서버(Node) 환경에서 ICU 데이터가 제한적이면 ko-KR이 폴백되어 "PM" 같은 문자열이 나올 수 있다.
  // - hydration mismatch를 막기 위해 AM/PM(오전/오후) 문자열이 나오지 않는 24시간 숫자 포맷으로 고정한다.
  return d.toLocaleString("ko-KR", {
    timeZone: DISPLAY_TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

/** null/undefined일 때 "" 반환 (라벨 등에서 사용) */
export function formatDateInSeoulOrEmpty(iso: string | null | undefined): string {
  const s = formatDateInSeoul(iso);
  return s === "-" ? "" : s;
}

