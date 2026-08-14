const TMDB_SIZE_PATTERN = /^(https:\/\/image\.tmdb\.org\/t\/p\/)w\d+(\/.*)$/i;
const LOCAL_WEBP_ASSET = /^\/images\/(?:characters\/|character\/mu\/|brand\/|posters\/today-us|promo\d)/;

export function optimizeImageUrl(value, tmdbSize = 'w342') {
  const url = String(value || '').trim();
  if (!url) return '';

  const tmdbMatch = url.match(TMDB_SIZE_PATTERN);
  if (tmdbMatch) return `${tmdbMatch[1]}${tmdbSize}${tmdbMatch[2]}`;
  if (LOCAL_WEBP_ASSET.test(url)) return url.replace(/\.png(?=\?|$)/i, '.webp');
  return url;
}
