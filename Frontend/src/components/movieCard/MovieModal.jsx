import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import { fetchMovieDetail } from '../../api.js';
import './movieModal.css';

let youtubeApiPromise;

function loadYouTubeApi() {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (youtubeApiPromise) return youtubeApiPromise;

  youtubeApiPromise = new Promise((resolve) => {
    const previousReady = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      previousReady?.();
      resolve(window.YT);
    };

    if (!document.querySelector('script[src="https://www.youtube.com/iframe_api"]')) {
      const script = document.createElement('script');
      script.src = 'https://www.youtube.com/iframe_api';
      script.async = true;
      document.head.appendChild(script);
    }
  });

  return youtubeApiPromise;
}

// 유튜브 watch/단축 링크를 임베드 가능한 형태로 변환
function toEmbeddableUrl(url) {
  if (!url) return '';

  const watchMatch = url.match(/youtube\.com\/watch\?v=([\w-]+)/);
  if (watchMatch) return `https://www.youtube.com/embed/${watchMatch[1]}`;

  const shortMatch = url.match(/youtu\.be\/([\w-]+)/);
  if (shortMatch) return `https://www.youtube.com/embed/${shortMatch[1]}`;

  return url;
}

function getYouTubeVideoId(url) {
  const match = String(url || '').match(
    /(?:youtube(?:-nocookie)?\.com\/(?:embed\/|watch\?v=)|youtu\.be\/)([\w-]+)/i
  );

  return match?.[1] || '';
}

function MovieModal({ movie, onClose, source = 'direct' }) {
  const [detail, setDetail] = useState(null);
  const [playerError, setPlayerError] = useState(null);
  const playerHostRef = useRef(null);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // 영화 상세 조회 → 로그인 상태면 조회 이력이 기록되어 "최근 본 영화"에 반영된다.
  const movieId = movie?.id ?? movie?.movie_id;
  useEffect(() => {
    setDetail(null);
    if (movieId === undefined || movieId === null) return undefined;

    const controller = new AbortController();
    fetchMovieDetail(movieId, source, controller.signal)
      .then(setDetail)
      .catch(() => {});

    return () => controller.abort();
  }, [movieId, source]);

  const movieTitle = detail?.title || movie?.title || '';
  const overview = detail?.overview || movie?.overview || '';
  const genreText =
    (Array.isArray(detail?.genres) ? detail.genres.join(', ') : '') ||
    movie?.genre ||
    '장르 정보 없음';
  const ratingText = detail?.vote_average ?? movie?.rating ?? '-';

  const trailerUrl = toEmbeddableUrl(
    detail?.trailer_url ||
      movie?.trailerUrl ||
      movie?.trailer_url ||
      movie?.trailer ||
      ''
  );
  const videoId = getYouTubeVideoId(trailerUrl);

  // 임베드가 불가능할 때(키 없음 등) 제목으로 유튜브에서 바로 예고편을 찾아볼 수 있게 한다.
  const searchUrl = `https://www.youtube.com/results?search_query=${encodeURIComponent(
    `${movieTitle} 예고편`
  )}`;
  const externalTrailerUrl = videoId
    ? `https://www.youtube.com/watch?v=${videoId}`
    : searchUrl;

  useEffect(() => {
    setPlayerError(null);
    if (!videoId || !playerHostRef.current) return undefined;

    let disposed = false;
    let player;

    loadYouTubeApi().then((YT) => {
      if (disposed || !playerHostRef.current) return;

      player = new YT.Player(playerHostRef.current, {
        width: '100%',
        height: '100%',
        videoId,
        playerVars: {
          origin: window.location.origin,
          playsinline: 1,
          rel: 0,
        },
        events: {
          onReady: (event) => {
            event.target.getIframe().referrerPolicy = 'strict-origin-when-cross-origin';
          },
          onError: (event) => {
            if (!disposed) setPlayerError(Number(event.data) || -1);
          },
        },
      });
    });

    return () => {
      disposed = true;
      try {
        player?.destroy();
      } catch (error) {
        // YouTube가 이미 iframe을 정리한 경우에는 추가 작업이 필요 없다.
      }
    };
  }, [videoId]);

  if (!movie) return null;

  // 부모(.app-shell)의 transform 때문에 fixed가 어긋나므로, body로 포털해 뷰포트 기준으로 띄운다.
  return createPortal(
    <div
      className="movie-modal-backdrop"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="movie-modal"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`${movieTitle} 상세 정보`}
      >
        <button
          className="movie-modal__close"
          type="button"
          onClick={onClose}
          aria-label="닫기"
        >
          ×
        </button>

        <div className="movie-modal__trailer">
          {playerError ? (
            <div className="movie-modal__trailer-empty movie-modal__trailer-empty--error">
              <strong>
                {[101, 150].includes(playerError)
                  ? '사이트 내 재생이 제한된 영상입니다.'
                  : '화면에서 예고편을 재생할 수 없습니다.'}
              </strong>
              <a
                className="movie-modal__trailer-search"
                href={externalTrailerUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                ▶ YouTube에서 재생하기
              </a>
            </div>
          ) : videoId ? (
            <div className="movie-modal__youtube-player" ref={playerHostRef} />
          ) : trailerUrl ? (
            <iframe
              src={trailerUrl}
              title={`${movieTitle} 예고편`}
              referrerPolicy="strict-origin-when-cross-origin"
              allow="autoplay; encrypted-media; picture-in-picture"
              allowFullScreen
            />
          ) : (
            <div className="movie-modal__trailer-empty">
              <a
                className="movie-modal__trailer-search"
                href={externalTrailerUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                ▶ YouTube에서 예고편 보기
              </a>
            </div>
          )}
        </div>

        <div className="movie-modal__info">
          <h1>{movieTitle}</h1>
          <h3>{genreText}</h3>
          <div className="movie-modal__rating">★ {ratingText}</div>
          {overview ? <p className="movie-modal__overview">{overview}</p> : null}
        </div>
      </div>
    </div>,
    document.body
  );
}

export default MovieModal;
