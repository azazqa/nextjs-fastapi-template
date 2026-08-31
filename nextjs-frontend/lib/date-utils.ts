const DISPLAY_TIMEZONE = "Asia/Seoul";

function parseApiDate(iso: string | null | undefined): Date | null {
  if (iso == null) return null;
  if (typeof iso !== "string") return null;
  let trimmed = iso.trim();
  if (!trimmed) return null;

  if (/^\d{4}-\d{2}-\d{2}\s+\d/.test(trimmed)) {
    trimmed = trimmed.replace(/^(\d{4}-\d{2}-\d{2})\s+/, "$1T");
  }

  const hasOffsetOrZ = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(trimmed);
  const normalized = hasOffsetOrZ ? trimmed : `${trimmed}Z`;
  const d = new Date(normalized);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDateTimeInSeoul(iso: string | null | undefined): string {
  const d = parseApiDate(iso);
  if (!d) return "-";
  return d.toLocaleString("sv-SE", { timeZone: DISPLAY_TIMEZONE });
}
