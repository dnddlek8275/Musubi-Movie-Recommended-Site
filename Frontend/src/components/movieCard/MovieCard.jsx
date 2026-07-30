import './movieCard.css';

function MovieCard({
  isLiked,
  movie,
  onToggleLike,
  onSelect,
  index,
  variant = 'default',
}) {
  const heart = isLiked ? '♥' : '♡';
  const posterUrl =
    movie?.posterUrl ||
    movie?.poster_url ||
    movie?.poster_path ||
    movie?.poster ||
    movie?.image_url ||
    movie?.image ||
    '';

  const handleClick = () => {
    if (onSelect) {
      onSelect(movie);
    } else {
      onToggleLike(movie);
    }
  };

  const handleHeartClick = (event) => {
    event.stopPropagation();
    onToggleLike(movie);
  };

  const stopHeartKeyDown = (event) => {
    event.stopPropagation();
  };

  const handleKeyDown = (event) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    handleClick();
  };

  if (variant === 'recent') {
    return (
      <article
        className={`recent-poster recent-poster--${index + 1}`}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={0}
      >
        {posterUrl ? (
          <img
            className="recent-poster__image"
            src={posterUrl}
            alt={`${movie.title} 포스터`}
          />
        ) : null}
        <span>{movie.title}</span>

        <button
          className={isLiked ? 'recent-heart recent-heart--active' : 'recent-heart'}
          type="button"
          onClick={handleHeartClick}
          onKeyDown={stopHeartKeyDown}
          aria-label={`${movie.title} 좋아요`}
        >
          {heart}
        </button>
      </article>
    );
  }

  return (
    <article
      className="movie-card"
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
    >
      <div className={`movie-card__poster movie-card__poster--${index + 1}`}>
        {posterUrl ? (
          <img
            className="movie-card__poster-image"
            src={posterUrl}
            alt={`${movie.title} 포스터`}
          />
        ) : null}

        <button
          className={isLiked ? 'movie-card__heart movie-card__heart--active' : 'movie-card__heart'}
          type="button"
          onClick={handleHeartClick}
          onKeyDown={stopHeartKeyDown}
          aria-label={`${movie.title} 좋아요`}
        >
          {heart}
        </button>
      </div>

      <div className="movie-card__info">
        <strong>{movie.title}</strong>
        <span>{movie.genre}</span>
        <div className="movie-card__rating">★ {movie.rating}</div>
      </div>
    </article>
  );
}

export default MovieCard;
