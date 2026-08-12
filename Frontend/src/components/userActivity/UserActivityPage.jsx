import { useEffect, useState } from 'react';

import { fetchPublicUserActivity, resolveMovieImage } from '../../api.js';
import { SkeletonBlock } from '../common/LoadingSkeleton.jsx';
import { getInternalMovieId } from '../../utils/movieIdentity.js';
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

function UserActivityPage({ userId }) {
  const [activity, setActivity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setStatus('');
    fetchPublicUserActivity(userId, controller.signal)
      .then(setActivity)
      .catch((error) => {
        if (error.name !== 'AbortError') setStatus(error.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [userId]);

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

      <section className="user-activity__section">
        <header><span>LIKED MOVIES</span><h2>좋아요 누른 영화</h2><small>{likedMovies.length}편</small></header>
        {likedMovies.length ? (
          <div className="user-activity__movie-grid">
            {likedMovies.map((movie) => {
              const id = getInternalMovieId(movie);
              const poster = resolveMovieImage(movie.poster_path || movie.poster_url || movie.poster);
              return (
                <a href={`/movies/${id}`} key={id}>
                  <div>{poster ? <img src={poster} alt="" loading="lazy" /> : <span>NO POSTER</span>}</div>
                  <strong>{movie.title || '영화'}</strong>
                </a>
              );
            })}
          </div>
        ) : <p className="user-activity__empty">공개할 좋아요 영화가 없습니다.</p>}
      </section>

      <section className="user-activity__section">
        <header><span>REVIEWS & RATINGS</span><h2>남긴 리뷰와 별점</h2><small>{reviews.length}건</small></header>
        {reviews.length ? (
          <div className="user-activity__review-grid">
            {reviews.map((review) => {
              const comment = String(review.comment || '').trim();
              return (
                <a href={`/movies/${getInternalMovieId(review.movie)}`} key={review.id}>
                  <header><strong>{review.movie?.title || '영화'}</strong><span>★ {review.score}</span></header>
                  <p className={!comment ? 'is-rating-only' : ''}>
                    {review.is_spoiler ? '스포일러가 포함된 리뷰입니다.' : comment || '별점만 남긴 평가입니다.'}
                  </p>
                  <time dateTime={review.updated_at}>{formatDate(review.updated_at)}</time>
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
