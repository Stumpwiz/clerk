// Titles considered single-incumbent offices where a vacancy placeholder is allowed.
// Matching is case-insensitive and trims whitespace when comparing.
export const SINGLE_INCUMBENT_TITLES: string[] = [
  "President",
  "Vice President",
  "Secretary",
  "Treasurer",
  "Chair",
];

export function isSingleIncumbentTitle(title?: string | null): boolean {
  const t = (title ?? "").trim().toLowerCase();
  if (!t) return false;
  return SINGLE_INCUMBENT_TITLES.some((x) => x.trim().toLowerCase() === t);
}
