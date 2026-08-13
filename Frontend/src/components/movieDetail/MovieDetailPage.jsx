import { useEffect, useMemo, useRef, useState } from 'react';

import {
  addLikedMovie,
  addWishlistMovie,
  deleteMovieRating,
  fetchLikedMovies,
  fetchMovieDetail,
  fetchSimilarMovies,
  fetchWishlistMovies,
  rateMovie,
  removeLikedMovie,
  removeWishlistMovie,
  resolveMovieImage,
} from '../../api.js';
import { navigateTo } from '../../navigation.js';
import { normalizeMovie } from '../index/RecommendationRow.jsx';
import { SkeletonBlock } from '../common/LoadingSkeleton.jsx';
import HorizontalScroller from '../common/HorizontalScroller.jsx';
import {
  getInternalMovieId,
  hasMatchingMovieIdentity,
} from '../../utils/movieIdentity.js';
import { formatRating } from '../../utils/formatRating.js';
import './movieDetail.css';

function toEmbedUrl(url) {
  const value = String(url || '');
  const match = value.match(/(?:youtube(?:-nocookie)?\.com\/(?:embed\/|watch\?v=)|youtu\.be\/)([\w-]+)/i);
  return match?.[1] ? `https://www.youtube.com/embed/${match[1]}` : '';
}

function youtubeThumbnail(url) {
  const embedUrl = toEmbedUrl(url);
  const videoId = embedUrl.split('/').pop();
  return videoId ? `https://img.youtube.com/vi/${videoId}/mqdefault.jpg` : '';
}

function formatDate(value, year) {
  if (value) return String(value).slice(0, 10).replaceAll('-', '.');
  return year ? `${year}` : '정보 없음';
}

function formatReviewDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date);
}

function formatProductionCountries(detail) {
  const countries = Array.isArray(detail?.production_countries)
    ? detail.production_countries.filter(Boolean)
    : [];
  if (!countries.length) return detail?.production_country || detail?.country || '정보 없음';
  try {
    const displayNames = new Intl.DisplayNames(['ko'], { type: 'region' });
    return countries.map((code) => displayNames.of(String(code).toUpperCase()) || code).join(' · ');
  } catch {
    return countries.join(' · ');
  }
}

function MovieDetailPage({ authUser, movieId }) {
  const trailerListRef = useRef(null);
  const [detail, setDetail] = useState(null);
  const [recommended, setRecommended] = useState([]);
  const [liked, setLiked] = useState(false);
  const [wishlisted, setWishlisted] = useState(false);
  const [rating, setRating] = useState(0);
  const [draftRating, setDraftRating] = useState(0);
  const [reviewComment, setReviewComment] = useState('');
  const [draftComment, setDraftComment] = useState('');
  const [reviewSpoiler, setReviewSpoiler] = useState(false);
  const [draftSpoiler, setDraftSpoiler] = useState(false);
  const [ratingOpen, setRatingOpen] = useState(false);
  const [ratingSaving, setRatingSaving] = useState(false);
  const [showAllCast, setShowAllCast] = useState(false);
  const [showAllReviews, setShowAllReviews] = useState(false);
  const [expandedReviews, setExpandedReviews] = useState([]);
  const [revealedSpoilers, setRevealedSpoilers] = useState([]);
  const [selectedTrailerUrl, setSelectedTrailerUrl] = useState('');
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true);
  const [recommendedLoading, setRecommendedLoading] = useState(true);
  const [posterFailed, setPosterFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setStatus('');

    fetchMovieDetail(movieId, new URLSearchParams(window.location.search).get('source') || 'direct', controller.signal)
      .then((movie) => {
        if (!hasMatchingMovieIdentity(movieId, movie)) {
          throw new Error('영화 식별 정보가 일치하지 않습니다. 페이지를 새로고침해 주세요.');
        }
        setDetail(movie);
        const savedRating = Number(movie?.my_rating) || 0;
        setRating(savedRating);
        setDraftRating(savedRating);
        const savedComment = String(movie?.my_comment || '');
        setReviewComment(savedComment);
        setDraftComment(savedComment);
        const savedSpoiler = Boolean(movie?.my_is_spoiler);
        setReviewSpoiler(savedSpoiler);
        setDraftSpoiler(savedSpoiler);
        const firstTrailer = movie?.trailer_videos?.[0]?.url || movie?.trailer_url || '';
        setSelectedTrailerUrl(toEmbedUrl(firstTrailer));
      })
      .catch((error) => {
        if (error.name !== 'AbortError') setStatus(error.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [movieId]);

  useEffect(() => {
    if (!authUser) return undefined;
    const controller = new AbortController();
    Promise.allSettled([fetchLikedMovies(controller.signal), fetchWishlistMovies(controller.signal)])
      .then(([likedResult, wishlistResult]) => {
        if (likedResult.status === 'fulfilled') {
          setLiked(likedResult.value.some((movie) => String(getInternalMovieId(movie)) === String(movieId)));
        }
        if (wishlistResult.status === 'fulfilled') {
          setWishlisted(wishlistResult.value.some((movie) => String(getInternalMovieId(movie)) === String(movieId)));
        }
        const rejected = [likedResult, wishlistResult].find((result) => result.status === 'rejected');
        if (rejected && rejected.reason?.name !== 'AbortError') setStatus(rejected.reason.message);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [authUser, movieId]);

  useEffect(() => {
    const controller = new AbortController();
    setRecommendedLoading(true);
    fetchSimilarMovies(movieId, controller.signal, 6)
      .then((movies) => {
        setRecommended(
          movies
            .map(normalizeMovie)
            .slice(0, 6)
        );
      })
      .catch(() => setRecommended([]))
      .finally(() => {
        if (!controller.signal.aborted) setRecommendedLoading(false);
      });
    return () => controller.abort();
  }, [movieId]);

  const reviews = Array.isArray(detail?.reviews) ? detail.reviews : [];
  const reviewAverage = useMemo(() => {
    const explicitValue = detail?.musubi_rating ?? detail?.review_average;
    const explicit = Number(explicitValue);
    if (explicitValue != null && Number.isFinite(explicit)) return explicit;
    if (!reviews.length) return null;
    return reviews.reduce((sum, review) => sum + Number(review.score || 0), 0) / reviews.length;
  }, [detail, reviews]);

  const castDetails = Array.isArray(detail?.cast_details)
    ? detail.cast_details.filter((actor) => actor?.name)
    : [];
  const cast = castDetails.length
    ? castDetails
    : (Array.isArray(detail?.cast) ? detail.cast.filter(Boolean) : []).map((name) => ({
        name,
        character_name: '',
        profile_path: '',
      }));
  const visibleCast = showAllCast ? cast : cast.slice(0, 8);
  const directorNames = String(detail?.director || '')
    .split(',')
    .map((name) => name.trim())
    .filter(Boolean);
  const visibleReviews = showAllReviews ? reviews : reviews.slice(0, 6);
  const poster = resolveMovieImage(detail?.poster_path || '');

  useEffect(() => {
    setPosterFailed(false);
  }, [poster]);

  const trailerVideos = Array.isArray(detail?.trailer_videos) && detail.trailer_videos.length
    ? detail.trailer_videos
    : detail?.trailer_url
      ? [{ url: detail.trailer_url, name: `${detail.title} 예고편`, type: 'Trailer' }]
      : [];
  const trailer = selectedTrailerUrl || toEmbedUrl(trailerVideos[0]?.url);
  const selectedTrailer = trailerVideos.find((video) => toEmbedUrl(video.url) === trailer);
  const genres = Array.isArray(detail?.genres) && detail.genres.length
    ? detail.genres.join(' · ')
    : '정보 없음';
  const productionCountries = formatProductionCountries(detail);
  const certification = detail?.certification
    ? `${detail.certification}${detail.certification_country ? ` (${detail.certification_country})` : ''}`
    : detail?.age_rating || '정보 없음';

  const handleLike = async () => {
    if (!authUser) {
      setStatus('좋아요는 로그인 후 이용할 수 있어요.');
      return;
    }
    const next = !liked;
    setLiked(next);
    setStatus('');
    try {
      if (next) await addLikedMovie({ id: movieId, title: detail?.title });
      else await removeLikedMovie({ id: movieId, title: detail?.title });
    } catch (error) {
      setLiked(!next);
      setStatus(error.message);
    }
  };

  const handleWishlist = async () => {
    if (!authUser) {
      setStatus('찜하기는 로그인 후 이용할 수 있어요.');
      return;
    }
    const next = !wishlisted;
    setWishlisted(next);
    setStatus('');
    try {
      if (next) await addWishlistMovie(movieId);
      else await removeWishlistMovie(movieId);
    } catch (error) {
      setWishlisted(!next);
      setStatus(error.message);
    }
  };

  const toggleRating = () => {
    if (!authUser) {
      setStatus('평가는 로그인 후 이용할 수 있어요.');
      return;
    }
    setDraftRating(rating || 0);
    setDraftComment(reviewComment);
    setDraftSpoiler(reviewSpoiler);
    setStatus('');
    setRatingOpen((open) => !open);
  };

  const handleRatingSave = async () => {
    if (!draftRating || ratingSaving) return;
    const verifiedMovieId = getInternalMovieId(detail);
    if (!verifiedMovieId || !hasMatchingMovieIdentity(movieId, detail)) {
      setStatus('영화 식별 정보가 일치하지 않아 리뷰를 저장하지 않았습니다. 페이지를 새로고침해 주세요.');
      return;
    }
    setRatingSaving(true);
    setStatus('');
    try {
      const result = await rateMovie(
        verifiedMovieId,
        draftRating,
        draftComment.trim(),
        {
          expectedMovieId: verifiedMovieId,
          expectedTmdbId: detail?.tmdb_id,
          expectedTitle: detail?.title,
          isSpoiler: draftSpoiler,
        }
      );
      setRating(Number(result.my_rating) || draftRating);
      setReviewComment(String(result.my_comment || ''));
      setReviewSpoiler(Boolean(result.my_is_spoiler ?? draftSpoiler));
      setDetail((current) => ({ ...current, ...result }));
      setRatingOpen(false);
      setStatus('');
    } catch (error) {
      setStatus(error.message);
    } finally {
      setRatingSaving(false);
    }
  };

  const handleRatingDelete = async () => {
    if (!rating || ratingSaving) return;
    const verifiedMovieId = getInternalMovieId(detail);
    if (!verifiedMovieId || !hasMatchingMovieIdentity(movieId, detail)) {
      setStatus('영화 식별 정보가 일치하지 않아 리뷰를 삭제하지 않았습니다. 페이지를 새로고침해 주세요.');
      return;
    }
    setRatingSaving(true);
    setStatus('');
    try {
      const result = await deleteMovieRating(verifiedMovieId, {
        expectedMovieId: verifiedMovieId,
        expectedTmdbId: detail?.tmdb_id,
        expectedTitle: detail?.title,
      });
      setRating(0);
      setDraftRating(0);
      setReviewComment('');
      setDraftComment('');
      setReviewSpoiler(false);
      setDraftSpoiler(false);
      setDetail((current) => ({ ...current, ...result }));
      setRatingOpen(false);
      setStatus('평가와 리뷰가 삭제되었습니다.');
    } catch (error) {
      setStatus(error.message);
    } finally {
      setRatingSaving(false);
    }
  };

  const scrollTrailerList = (direction) => {
    const list = trailerListRef.current;
    if (!list) return;
    list.scrollBy({ left: direction * list.clientWidth * 0.72, behavior: 'smooth' });
  };

  const toggleReview = (reviewId) => {
    const id = String(reviewId);
    setExpandedReviews((current) => (
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
    ));
  };

  const openMemberActivityPage = (review) => {
    if (!review?.user_id || review.is_mine) return;
    navigateTo(`/users/${encodeURIComponent(review.user_id)}/activity`);
  };

  if (loading) {
    return (
      <main className="movie-detail movie-detail--skeleton" aria-busy="true" aria-label="영화 정보 불러오는 중">
        <section className="movie-detail-skeleton__hero" aria-hidden="true">
          <SkeletonBlock className="movie-detail-skeleton__poster" />
          <div className="movie-detail-skeleton__story">
            <SkeletonBlock className="movie-detail-skeleton__title" />
            <SkeletonBlock className="loading-skeleton--line loading-skeleton--short" />
            <SkeletonBlock className="loading-skeleton--line" />
            <SkeletonBlock className="loading-skeleton--line" />
            <SkeletonBlock className="loading-skeleton--line loading-skeleton--short" />
            <div className="movie-detail-skeleton__buttons">
              <SkeletonBlock />
              <SkeletonBlock />
            </div>
          </div>
        </section>
        <div className="movie-detail-skeleton__metadata" aria-hidden="true">
          {Array.from({ length: 5 }, (_, index) => <SkeletonBlock key={index} />)}
        </div>
        <div className="movie-detail-skeleton__columns" aria-hidden="true">
          <SkeletonBlock />
          <SkeletonBlock />
        </div>
      </main>
    );
  }

  if (!detail) {
    return <main className="movie-detail movie-detail--empty">{status || '영화 정보를 찾을 수 없습니다.'}</main>;
  }

  return (
    <main className="movie-detail">
      <section className="movie-detail__hero">
        <div className="movie-detail__poster">
          {poster && !posterFailed ? (
            <img
              src={poster}
              alt={`${detail.title} 포스터`}
              decoding="async"
              fetchPriority="high"
              onError={() => setPosterFailed(true)}
            />
          ) : (
            <div
              className="movie-detail__poster-placeholder"
              role="img"
              aria-label={`${detail.title} 포스터 준비 중`}
            >
              <span className="movie-detail__poster-placeholder-mark" aria-hidden="true">M</span>
              <span className="movie-detail__poster-placeholder-brand">MUSUBI</span>
              <strong>{detail.title}</strong>
              <small>포스터 준비 중</small>
            </div>
          )}
        </div>

        <div className="movie-detail__story">
          <h1 className="movie-detail__title">{detail.title}</h1>
          <span className="movie-detail__eyebrow">STORY</span>
          <h2>줄거리</h2>
          <p>{detail.overview || '등록된 줄거리 정보가 없습니다.'}</p>
          <div className="movie-detail__actions">
            <button type="button" onClick={handleLike}>
              <span className={liked ? 'movie-detail__heart is-liked' : 'movie-detail__heart'}>{liked ? '♥' : '♡'}</span> 좋아요
            </button>
            <button className={wishlisted ? 'is-wishlisted' : ''} type="button" onClick={handleWishlist}>
              <span className="movie-detail__bookmark" aria-hidden="true">{wishlisted ? '★' : '☆'}</span>
              찜하기
            </button>
            <button type="button" onClick={toggleRating}>
              평가하기
            </button>
          </div>
          {ratingOpen ? (
            <div className="movie-detail__rating-panel">
              <strong>이 영화는 어떠셨나요?</strong>
              <div className="movie-detail__rating-stars" role="group" aria-label="영화 평점 선택">
                {[1, 2, 3, 4, 5].map((score) => (
                  <button
                    aria-label={`${score - 0.5}점 또는 ${score}점 선택`}
                    aria-pressed={draftRating === score || draftRating === score - 0.5}
                    key={score}
                    onClick={(event) => {
                      if (event.detail === 0) {
                        setDraftRating(score);
                        return;
                      }
                      const rect = event.currentTarget.getBoundingClientRect();
                      setDraftRating(event.clientX - rect.left < rect.width / 2 ? score - 0.5 : score);
                    }}
                    style={{ '--rating-fill': `${Math.max(0, Math.min(1, draftRating - score + 1)) * 25}px` }}
                    type="button"
                  >
                    <span className="movie-detail__rating-star-base" aria-hidden="true">★</span>
                    <span className="movie-detail__rating-star-fill" aria-hidden="true">★</span>
                  </button>
                ))}
              </div>
              <label className="movie-detail__review-input">
                <span>한줄 리뷰 <small>선택사항</small></span>
                <textarea
                  maxLength="500"
                  onChange={(event) => setDraftComment(event.target.value)}
                  placeholder="이 영화에 대한 생각을 남겨주세요."
                  rows="3"
                  value={draftComment}
                />
                <small>{draftComment.length}/500</small>
              </label>
              <label className="movie-detail__spoiler-check">
                <input checked={draftSpoiler} onChange={(event) => setDraftSpoiler(event.target.checked)} type="checkbox" />
                <span>스포일러가 포함된 리뷰예요</span>
              </label>
              <div className="movie-detail__rating-controls">
                {rating ? (
                  <button className="movie-detail__rating-delete" disabled={ratingSaving} onClick={handleRatingDelete} type="button">
                    내 평가 삭제
                  </button>
                ) : null}
                <button
                  className="movie-detail__rating-submit"
                  disabled={!draftRating || ratingSaving}
                  onClick={handleRatingSave}
                  type="button"
                >{ratingSaving ? '저장 중…' : rating ? '평가 및 리뷰 수정' : '평가 및 리뷰 등록'}</button>
              </div>
            </div>
          ) : null}
          {status ? <p className="movie-detail__status" role="status">{status}</p> : null}

          <dl className="movie-detail__metadata">
            <div><dt>장르</dt><dd>{genres}</dd></div>
            <div><dt>공개일</dt><dd>{formatDate(detail.release_date, detail.year)}</dd></div>
            <div><dt>러닝타임</dt><dd>{detail.runtime ? `${detail.runtime}분` : '정보 없음'}</dd></div>
            <div><dt>제작국가</dt><dd>{productionCountries}</dd></div>
            <div><dt>연령등급</dt><dd>{certification}</dd></div>
          </dl>
        </div>
      </section>

      <section className="movie-detail__community">
        <div className="movie-detail__cast">
          <div className="movie-detail__director">
            <div className="movie-detail__section-heading"><span>DIRECTOR</span><h2>감독</h2></div>
            <div className="movie-detail__cast-grid movie-detail__director-grid">
              {directorNames.length ? directorNames.map((director) => (
                <a href={`/people/director/${encodeURIComponent(director)}`} key={director}>
                  <span className="movie-detail__cast-avatar" aria-hidden="true">{director.slice(0, 1)}</span>
                  <span className="movie-detail__cast-info">
                    <strong>{director}</strong>
                    <small>필모그래피 보기</small>
                  </span>
                </a>
              )) : <article><strong>정보 없음</strong></article>}
            </div>
          </div>
          <div className="movie-detail__section-heading"><span>CAST</span><h2>출연진</h2></div>
          {visibleCast.length ? (
            <div className="movie-detail__cast-grid">
              {visibleCast.map((actor) => (
                <a
                  href={`/people/actor/${encodeURIComponent(actor.actor_id || actor.name)}`}
                  key={actor.actor_id || `${actor.name}-${actor.character_name}`}
                >
                  <span className="movie-detail__cast-avatar" aria-hidden="true">
                    {actor.profile_path
                      ? <img src={actor.profile_path} alt="" decoding="async" loading="lazy" />
                      : String(actor.name).slice(0, 1)}
                  </span>
                  <span className="movie-detail__cast-info">
                    <strong>{actor.name}</strong>
                    {actor.character_name ? <small>{actor.character_name}</small> : null}
                  </span>
                </a>
              ))}
            </div>
          ) : <p className="movie-detail__empty-copy">등록된 출연진 정보가 없습니다.</p>}
          {cast.length > 8 ? (
            <button className="movie-detail__more" type="button" onClick={() => setShowAllCast((value) => !value)}>
              {showAllCast ? '접기' : `+ ${cast.length - 8}명 더보기`}
            </button>
          ) : null}
        </div>

        <div className="movie-detail__reviews">
          <div className="movie-detail__section-heading"><span>MUSUBI REVIEW</span><h2>무스비 리뷰 & 평점</h2></div>
          <div className="movie-detail__review-score">
            <strong>{reviewAverage === null ? '평가 전' : reviewAverage.toFixed(1)}</strong>
            <span>{reviewAverage === null ? '☆☆☆☆☆' : `${'★'.repeat(Math.round(reviewAverage))}${'☆'.repeat(5 - Math.round(reviewAverage))}`}</span>
            <small>{detail.rating_count ? `${detail.rating_count}명의 평가` : '첫 번째 평가를 기다리고 있어요'}</small>
          </div>
          {visibleReviews.length ? (
            <div className="movie-detail__review-grid">
              {visibleReviews.map((review, index) => {
                const isMemberReview = Boolean(review.user_id && !review.is_mine);
                return (
                <article
                  aria-label={isMemberReview ? `${review.nickname || '사용자'}의 활동 페이지로 이동` : undefined}
                  className={`movie-detail__review${isMemberReview ? ' is-member-link' : ''}`}
                  key={review.id ?? index}
                  onClick={isMemberReview ? () => openMemberActivityPage(review) : undefined}
                  onKeyDown={isMemberReview ? (event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      openMemberActivityPage(review);
                    }
                  } : undefined}
                  role={isMemberReview ? 'link' : undefined}
                  tabIndex={isMemberReview ? 0 : undefined}
                >
                  <strong className="movie-detail__review-author">{review.nickname || '사용자'}</strong>
                  <div className="movie-detail__review-meta">
                    <time dateTime={review.updated_at}>{formatReviewDate(review.updated_at)}</time>
                    <span>★ {formatRating(review.score)}</span>
                  </div>
                  {review.is_spoiler && !revealedSpoilers.includes(String(review.id ?? index)) ? (
                    <button className="movie-detail__spoiler-cover" onClick={(event) => { event.stopPropagation(); setRevealedSpoilers((current) => [...current, String(review.id ?? index)]); }} type="button">
                      스포일러가 포함되어 있습니다. 눌러서 보기
                    </button>
                  ) : <p className={expandedReviews.includes(String(review.id ?? index)) ? 'is-expanded' : ''}>{review.comment}</p>}
                  {(!review.is_spoiler || revealedSpoilers.includes(String(review.id ?? index))) && String(review.comment || '').length > 90 ? (
                    <button className="movie-detail__review-more" onClick={(event) => { event.stopPropagation(); toggleReview(review.id ?? index); }} type="button">
                      {expandedReviews.includes(String(review.id ?? index)) ? '접기' : '더보기'}
                    </button>
                  ) : null}
                </article>
                );
              })}
            </div>
          ) : <p className="movie-detail__empty-copy">아직 작성된 Musubi 리뷰가 없습니다.</p>}
          {reviews.length > 6 ? (
            <button className="movie-detail__more" type="button" onClick={() => setShowAllReviews((value) => !value)}>
              {showAllReviews ? '리뷰 접기' : '리뷰 더보기'}
            </button>
          ) : null}
        </div>
      </section>

      <section className="movie-detail__trailer">
        <div className="movie-detail__section-heading"><span>TRAILER</span><h2>영화 예고편</h2></div>
        {trailer ? (
          <div className="movie-detail__trailer-player">
            <iframe src={trailer} title={selectedTrailer?.name || `${detail.title} 예고편`} allow="autoplay; encrypted-media; picture-in-picture" allowFullScreen />
          </div>
        ) : (
          <a href={`https://www.youtube.com/results?search_query=${encodeURIComponent(`${detail.title} 예고편`)}`} target="_blank" rel="noreferrer">
            YouTube에서 예고편 찾아보기 ↗
          </a>
        )}
        {trailerVideos.length > 1 ? (
          <div className="movie-detail__trailer-carousel">
            <button aria-label="이전 영상 보기" className="movie-detail__trailer-arrow is-prev" onClick={() => scrollTrailerList(-1)} type="button">‹</button>
            <div className="movie-detail__trailer-list" aria-label="추가 영상" ref={trailerListRef}>
              {trailerVideos.map((video) => {
                const videoUrl = toEmbedUrl(video.url);
                return (
                  <button className={videoUrl === trailer ? 'is-active' : ''} key={video.url} onClick={() => setSelectedTrailerUrl(videoUrl)} type="button">
                    <img src={youtubeThumbnail(video.url)} alt="" decoding="async" loading="lazy" />
                    <span><strong>{video.name}</strong><small>{video.type}</small></span>
                  </button>
                );
              })}
            </div>
            <button aria-label="다음 영상 보기" className="movie-detail__trailer-arrow is-next" onClick={() => scrollTrailerList(1)} type="button">›</button>
          </div>
        ) : null}
      </section>

      <section className="movie-detail__similar">
        <div className="movie-detail__section-heading"><span>MORE LIKE THIS</span><h2>이런 영화를 좋아하신다면?</h2></div>
        <HorizontalScroller className="movie-detail__similar-grid" ariaLabel="비슷한 추천 영화 목록">
          {recommendedLoading ? Array.from({ length: 6 }, (_, index) => (
            <div className="movie-detail__similar-skeleton" key={`similar-skeleton-${index}`} aria-hidden="true">
              <SkeletonBlock />
              <SkeletonBlock className="loading-skeleton--line" />
              <SkeletonBlock className="loading-skeleton--line loading-skeleton--short" />
            </div>
          )) : recommended.map((movie) => (
            <a href={`/movies/${movie.id}`} key={movie.id}>
              <div>{movie.poster ? <img src={movie.poster} alt="" decoding="async" loading="lazy" /> : <span>NO POSTER</span>}</div>
              <strong>{movie.title}</strong>
              <small>{movie.genre}</small>
            </a>
          ))}
        </HorizontalScroller>
        {!recommendedLoading && recommended.length === 0 ? <p className="movie-detail__empty-copy">추천 영화를 준비하지 못했습니다.</p> : null}
      </section>

    </main>
  );
}

export default MovieDetailPage;
