import { optimizeImageUrl } from '../../utils/imagePerformance.js';

const POSTER_BASE_URL =
  import.meta.env.VITE_TMDB_IMAGE_BASE_URL || 'https://image.tmdb.org/t/p/w500';

function toPosterUrl(value) {
  const path = String(value || '').trim();

  if (!path) return '';
  if (/^(https?:|data:|blob:)/i.test(path)) return path;
  return `${POSTER_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}

function PosterArt({ movie, compact = false }) {
  const className = compact ? 'index-mini-poster' : 'index-poster-art';
  const posterUrl = optimizeImageUrl(toPosterUrl(
    movie.posterUrl ||
      movie.poster_url ||
      movie.poster_path ||
      movie.poster ||
      movie.image_url ||
      movie.image ||
      ''
  ), 'w342');

  return (
    <div className={className}>
      {posterUrl ? (
        <img src={posterUrl} alt={`${movie.title} 포스터`} decoding="async" loading="lazy" />
      ) : null}
    </div>
  );
}

export default PosterArt;
