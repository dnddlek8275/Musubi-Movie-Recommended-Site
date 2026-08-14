export function formatRating(value, fallback = '-') {
  if (value === null || value === undefined || value === '') return fallback;
  const rating = Number(value);
  return Number.isFinite(rating) ? rating.toFixed(1) : fallback;
}
