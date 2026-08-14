import { useEffect, useRef, useState } from 'react';

import {
  addLikedMovie,
  fetchLikedMovies,
  fetchPublicUserActivity,
  removeLikedMovie,
  resolveMovieImage,
} from '../../api.js';
import { SkeletonBlock } from '../common/LoadingSkeleton.jsx';
import HorizontalScroller from '../common/HorizontalScroller.jsx';
import { getInternalMovieId } from '../../utils/movieIdentity.js';
import { formatRating } from '../../utils/formatRating.js';
import '../mypage/mypage.css';
import './userActivity.css';

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date);
}

function UserMovieGrid({ authUser, movies, likedIds, onToggleLike, hideScrollbar = false }) {
  const railRef = useRef(null);

  const startDrag = (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (event.pointerType !== 'mouse' || event.button !== 0 || target?.closest('button')) return;
    const rail = railRef.current;
    if (!rail || rail.scrollWidth <= rail.clientWidth) return;
    rail.dataset.dragging = 'true';
    rail.dataset.moved = 'false';
    rail.dataset.startX = String(event.clientX);
    rail.dataset.startScroll = String(rail.scrollLeft);
    rail.setPointerCapture(event.pointerId);
  };

  const moveDrag = (event) => {
    const rail = railRef.current;
    if (!rail || rail.dataset.dragging !== 'true') return;
    const distance = event.clientX - Number(rail.dataset.startX || event.clientX);
    if (Math.abs(distance) > 4) rail.dataset.moved = 'true';
    rail.scrollLeft = Number(rail.dataset.startScroll || 0) - distance;
  };

  const stopDrag = (event) => {
    const rail = railRef.current;
    if (!rail || rail.dataset.dragging !== 'true') return;
    rail.dataset.dragging = 'false';
    if (rail.hasPointerCapture(event.pointerId)) rail.releasePointerCapture(event.pointerId);
  };

  const blockClickAfterDrag = (event) => {
    const rail = railRef.current;
    if (rail?.dataset.moved !== 'true') return;
    event.preventDefault();
    event.stopPropagation();
    rail.dataset.moved = 'false';
  };

  return (
    <HorizontalScroller
      ariaLabel="영화 목록"
      className={`user-activity__movie-grid${hideScrollbar ? ' is-scrollbar-hidden' : ''}`}
      externalRef={railRef}
      railProps={{
        onClickCapture: blockClickAfterDrag,
        onPointerCancel: stopDrag,
        onPointerDown: startDrag,
        onPointerMove: moveDrag,
        onPointerUp: stopDrag,
      }}
    >
      {movies.map((movie) => {
        const id = getInternalMovieId(movie);
        const poster = resolveMovieImage(movie.poster_path || movie.poster_url || movie.poster);
        const liked = likedIds.has(String(id));
        return (
          <article key={id}>
            <div>
              <a href={`/movies/${id}`} aria-label={`${movie.title || '영화'} 상세 보기`} />
              {poster ? <img src={poster} alt="" draggable="false" loading="lazy" /> : <span>NO POSTER</span>}
              {authUser ? <button className={liked ? 'is-liked' : ''} type="button" onClick={() => onToggleLike(movie)} aria-label={`${movie.title || '영화'} 좋아요 ${liked ? '취소' : '추가'}`}>{liked ? '♥' : '♡'}</button> : null}
            </div>
            <a className="user-activity__movie-title" href={`/movies/${id}`}>{movie.title || '영화'}</a>
          </article>
        );
      })}
    </HorizontalScroller>
  );
}

function UserActivityPage({ authUser, userId }) {
  const [activity, setActivity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('');
  const [likedIds, setLikedIds] = useState(new Set());

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setStatus('');
    Promise.all([
      fetchPublicUserActivity(userId, controller.signal),
      authUser ? fetchLikedMovies(controller.signal).catch(() => []) : Promise.resolve([]),
    ])
      .then(([nextActivity, myLikes]) => {
        setActivity(nextActivity);
        setLikedIds(new Set(myLikes.map((movie) => String(getInternalMovieId(movie)))));
      })
      .catch((error) => {
        if (error.name !== 'AbortError') setStatus(error.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [authUser?.email, userId]);

  const toggleLike = async (movie) => {
    const id = String(getInternalMovieId(movie));
    if (!id) return;
    const wasLiked = likedIds.has(id);
    setLikedIds((current) => {
      const next = new Set(current);
      if (wasLiked) next.delete(id); else next.add(id);
      return next;
    });
    setStatus('');
    try {
      if (wasLiked) await removeLikedMovie(movie);
      else await addLikedMovie(movie);
    } catch (error) {
      setLikedIds((current) => {
        const next = new Set(current);
        if (wasLiked) next.add(id); else next.delete(id);
        return next;
      });
      setStatus(error.message);
    }
  };

  if (loading) {
    return (
      <main className="user-activity user-activity--loading" aria-busy="true" aria-label="회원 활동 불러오는 중">
        <SkeletonBlock className="user-activity__profile-skeleton" />
        <div className="user-activity__movie-grid" aria-hidden="true">
          {Array.from({ length: 6 }, (_, index) => <SkeletonBlock key={index} />)}
        </div>
      </main>
    );
  }

  if (!activity) {
    return <main className="user-activity user-activity--empty">{status || '회원 활동을 불러오지 못했습니다.'}</main>;
  }

  const user = activity.user || {};
  const likedMovies = activity.liked_movies || [];
  const reviews = activity.reviews || [];

  return (
    <main className="user-activity">
      <header className="user-activity__profile">
        <div className="user-activity__avatar">
          {user.profile_image ? <img src={user.profile_image} alt="" /> : <span>{String(user.nickname || '회').slice(0, 1)}</span>}
        </div>
        <div>
          <span>MEMBER ACTIVITY</span>
          <h1>{user.nickname || '회원'}</h1>
          <p>좋아요 누른 영화와 남긴 리뷰를 모아봤어요.</p>
        </div>
      </header>

      {status ? <p className="user-activity__status" role="status">{status}</p> : null}

      <section className="user-activity__section">
        <header><span>LIKED MOVIES</span><h2>좋아요 누른 영화</h2><small>{likedMovies.length}편</small></header>
        {likedMovies.length
          ? <UserMovieGrid authUser={authUser} movies={likedMovies} likedIds={likedIds} onToggleLike={toggleLike} hideScrollbar />
          : <p className="user-activity__empty">공개할 좋아요 영화가 없습니다.</p>}
      </section>

      <section className="user-activity__section">
        <header><span>REVIEWS & RATINGS</span><h2>남긴 리뷰와 별점</h2><small>{reviews.length}건</small></header>
        {reviews.length ? (
          <div className="mypage-review-list">
            {reviews.map((review) => {
              const movie = review.movie || {};
              const id = getInternalMovieId(movie);
              const poster = resolveMovieImage(movie.poster_path || movie.poster_url || movie.poster);
              const comment = String(review.comment || '').trim();
              return (
                <a className="mypage-review-card" href={`/movies/${id}`} key={review.id}>
                  <div className="mypage-review-card__poster">{poster ? <img src={poster} alt="" loading="lazy" /> : <span>포스터 준비 중</span>}</div>
                  <div className="mypage-review-card__body">
                    <header><strong>{movie.title || '영화'}</strong><span>★ {formatRating(review.score)}</span></header>
                    <p className={!comment ? 'is-rating-only' : ''}>{review.is_spoiler ? '스포일러가 포함된 리뷰입니다.' : comment || '별점만 남긴 평가입니다.'}</p>
                    <time dateTime={review.updated_at}>{formatDate(review.updated_at)}</time>
                  </div>
                  <b aria-hidden="true">›</b>
                </a>
              );
            })}
          </div>
        ) : <p className="user-activity__empty">공개할 리뷰가 없습니다.</p>}
      </section>
    </main>
  );
}

export default UserActivityPage;
