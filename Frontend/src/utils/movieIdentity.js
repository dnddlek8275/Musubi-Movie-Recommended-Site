function toPositiveInteger(value) {
  if (value === null || value === undefined || value === '') return null;

  const normalized = Number(value);
  return Number.isSafeInteger(normalized) && normalized > 0 ? normalized : null;
}

// 상세 페이지 URL은 PostgreSQL movies.id만 사용한다.
// TMDB ID는 외부 식별자이므로 내부 movie_id의 대체값으로 사용하지 않는다.
export function getInternalMovieId(movie) {
  return toPositiveInteger(movie?.movie_id) ?? toPositiveInteger(movie?.id);
}

export function normalizeInternalMovieId(value) {
  return toPositiveInteger(value);
}

export function hasMatchingMovieIdentity(routeMovieId, detail) {
  const routeId = normalizeInternalMovieId(routeMovieId);
  const detailId = getInternalMovieId(detail);
  return routeId !== null && detailId !== null && routeId === detailId;
}
