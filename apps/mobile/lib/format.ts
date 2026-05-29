// Shared display formatters. Previously copy-pasted across index, clusters,
// cluster/[id] and profile — consolidated here so the rules stay consistent.

// snake_case / lower → Title Case, e.g. "water_supply" → "Water Supply".
export function humanize(raw: string): string {
  if (!raw) return "—";
  return raw.replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
}

// Compact age badge from an ISO timestamp: "3H", "5D", "2W".
export function relativeAge(iso: string): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  const diffMs = Date.now() - then;
  const day = 24 * 3600 * 1000;
  const days = Math.floor(diffMs / day);
  if (days < 1) {
    const h = Math.floor(diffMs / (3600 * 1000));
    return `${Math.max(1, h)}H`;
  }
  if (days < 14) return `${days}D`;
  return `${Math.floor(days / 7)}W`;
}

// BCP-47-ish language codes → human labels. Falls back to the raw code so an
// unmapped language still renders something rather than blanking.
const LANGUAGE_LABELS: Record<string, string> = {
  "hi-Latn": "Hinglish",
  hi: "Hindi",
  mr: "Marathi",
  ta: "Tamil",
  en: "English",
};

export function humanLanguage(code: string): string {
  if (!code) return "—";
  return LANGUAGE_LABELS[code] ?? code;
}

// Whole-days-since-created badge, e.g. "3d", for "3d Open" cluster figures.
export function daysOpenLabel(iso: string): string {
  if (!iso) return "—";
  const days = Math.max(
    0,
    Math.floor((Date.now() - new Date(iso).getTime()) / (24 * 3600 * 1000))
  );
  return `${days}d`;
}
