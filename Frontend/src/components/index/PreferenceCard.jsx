import { useEffect, useState } from 'react';

import { fetchUserPreferences, getLocalPreferences } from '../../api.js';
import { SkeletonBlock } from '../common/LoadingSkeleton.jsx';
import { getKeywordLabel } from '../../utils/keywordLabels.js';

const MU_MASCOTS = [
  { src: '/images/character/mu/mu-default-v1.webp', shiftX: '-2.4%', shiftY: '1%' },
  { src: '/images/character/mu/mu-searching-v2.webp', shiftX: '4.2%', shiftY: '1.3%' },
  { src: '/images/character/mu/mu-pose-popcorn-v1.webp', shiftX: '3%', shiftY: '0.7%' },
  { src: '/images/character/mu/mu-pose-drink-v1.webp', shiftX: '-1.2%', shiftY: '0' },
  { src: '/images/character/mu/mu-pose-watching-v1.webp', shiftX: '3.9%', shiftY: '-3%' },
];

function PreferenceCard({ authUser }) {
  const [mascot] = useState(
    () => MU_MASCOTS[Math.floor(Math.random() * MU_MASCOTS.length)],
  );
  const [nickname, setNickname] = useState(authUser?.nickname || '');
  const [preferences, setPreferences] = useState({
    genres: [],
    actors: [],
    keywords: [],
  });
  const [loading, setLoading] = useState(Boolean(authUser));

  useEffect(() => {
    const loginNickname =
      authUser?.nickname ||
      authUser?.name ||
      authUser?.username ||
      '';

    if (loginNickname) {
      setNickname(loginNickname);
    }
  }, [authUser]);

  useEffect(() => {
    if (!authUser) {
      setNickname('게스트');
      setPreferences(getLocalPreferences());
      setLoading(false);
      return undefined;
    }

    const controller = new AbortController();
    setLoading(true);

    const fetchPreferenceData = async () => {
      try {
        const data = await fetchUserPreferences(controller.signal);

        const user = data.user || data.member || data;

        const nextNickname =
          user.nickname ||
          user.name ||
          user.username ||
          data.nickname ||
          data.name ||
          data.username ||
          '';

        if (nextNickname) {
          setNickname(nextNickname);
        }

        setPreferences({
          genres: data.preferences?.genres || data.genres || [],
          actors: data.preferences?.actors || data.actors || [],
          keywords: data.preferences?.keywords || data.keywords || [],
        });
      } catch (error) {
        if (error.name === 'AbortError') return;

        console.error('취향 정보 불러오기 실패:', error);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };

    fetchPreferenceData();

    return () => controller.abort();
  }, [authUser]);

  return (
    <>
      <style>
        {`
          .index-taste-card {
            position: relative;
            width: 100%;
            height: 630px;
            padding: 62px 30px;
            border-radius: 16px;
            background: var(--panel);
            border: 1px solid var(--panel-border);
            color: var(--text);
            overflow: hidden;
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
          }

          .taste-card-more {
            position: absolute;
            top: 25px;
            right: 30px;
            font-size: 13px;
            font-weight: 600;
            color: var(--text);
            text-decoration: none;
            opacity: 0.95;
            cursor: pointer;
          }

          .taste-card-more:hover {
            text-decoration: underline;
          }

          .taste-card-header h2 {
            margin: 0 0 10px;
            font-size: 23px;
            font-weight: 800;
            line-height: 1.3;
            letter-spacing: -0.7px;
          }

          .taste-card-header p {
            margin: 0;
            font-size: 15px;
            font-weight: 500;
            color: var(--text);
            opacity: 0.9;
            letter-spacing: -0.3px;
          }

          .taste-card-preferences {
            display: flex;
            flex-direction: column;
            gap: 13px;
          }

          .taste-row {
            display: grid;
            grid-template-columns: 96px minmax(0, 1fr);
            align-items: flex-start;
            column-gap: 16px;
          }

          .taste-row strong {
            padding-top: 5px;
            font-size: 16px;
            font-weight: 800;
            color: var(--text);
            white-space: nowrap;
          }

          .taste-tags {
            min-width: 0;
            max-height: 52px;
            display: flex;
            flex-wrap: wrap;
            justify-content: flex-start;
            align-content: flex-start;
            align-items: flex-start;
            gap: 8px;
            overflow: hidden;
            text-align: left;
          }

          .taste-tags span {
            min-width: 44px;
            height: 22px;
            padding: 0 13px;
            border: 1px solid var(--line);
            border-radius: 999px;
            color: var(--text);
            font-size: 13px;
            font-weight: 700;
            line-height: 20px;
            text-align: center;
            box-sizing: border-box;
            background: transparent;
          }

          .taste-empty {
            padding-top: 4px;
            font-size: 13px;
            color: var(--muted);
          }

          .taste-card-mascot {
            display: block;
            align-self: center;
            width: 330px;
            height: 300px;
            margin: 0 auto;
            object-fit: contain;
            object-position: center;
            transform: translate(
              var(--mascot-shift-x, 0),
              var(--mascot-shift-y, 0)
            );
            pointer-events: none;
            user-select: none;
            filter:
              drop-shadow(0 16px 30px color-mix(in srgb, var(--accent) 18%, transparent))
              drop-shadow(0 0 24px rgba(255, 255, 255, 0.12));
          }

          .taste-card-loading {
            position: absolute;
            inset: 28px 30px;
            z-index: 4;
            display: grid;
            grid-template-rows: auto 1fr auto;
            gap: 28px;
            background: var(--panel);
          }

          .taste-card-loading__copy {
            display: grid;
            gap: 10px;
          }

          .taste-card-loading__copy .loading-skeleton:first-child {
            width: 48%;
            height: 24px;
            border-radius: 7px;
          }

          .taste-card-loading__copy .loading-skeleton:last-child {
            width: 72%;
            height: 14px;
            border-radius: 999px;
          }

          .taste-card-loading__mascot {
            width: 230px;
            height: 260px;
            margin: auto;
            border-radius: 46% 46% 34% 34%;
          }

          .taste-card-loading__tags {
            display: grid;
            gap: 14px;
          }

          .taste-card-loading__tags .loading-skeleton {
            width: 72%;
            height: 22px;
            border-radius: 999px;
          }

          @media (max-width: 768px) {
            .index-taste-card {
              height: auto;
              padding: 26px 22px;
              gap: 22px;
            }

            .taste-card-header h2 {
              font-size: 20px;
            }

            .taste-card-header p {
              font-size: 14px;
            }

            .taste-card-mascot {
              width: 150px;
              height: 150px;
            }
          }
        `}
      </style>

      <aside className="index-taste-card" aria-label="취향 분석">
        {loading ? (
          <div className="taste-card-loading" aria-hidden="true">
            <div className="taste-card-loading__copy">
              <SkeletonBlock />
              <SkeletonBlock />
            </div>
            <SkeletonBlock className="taste-card-loading__mascot" />
            <div className="taste-card-loading__tags">
              <SkeletonBlock />
              <SkeletonBlock />
              <SkeletonBlock />
            </div>
          </div>
        ) : null}
        <a href="/home" className="taste-card-more">
          내 취향 분석하기
        </a>

        <div className="taste-card-header">
          <h2>{nickname ? `${nickname}님! 안녕하세요,` : '안녕하세요!'}</h2>
          <p>
            {nickname
              ? `최근 대화를 통해 ${nickname}님의 취향을 분석했어요!`
              : '로그인을 해주세요'}
          </p>
        </div>

        <img
          className="taste-card-mascot"
          src={mascot.src}
          style={{
            '--mascot-shift-x': mascot.shiftX,
            '--mascot-shift-y': mascot.shiftY,
          }}
          alt=""
          aria-hidden="true"
        />

        <div className="taste-card-preferences">
          <div className="taste-row">
            <strong>선호 장르</strong>
            <div className="taste-tags">
              {preferences.genres.length > 0 ? (
                preferences.genres.slice(0, 3).map((genre) => (
                  <span key={genre}>{genre}</span>
                ))
              ) : (
                <em className="taste-empty">분석 전</em>
              )}
            </div>
          </div>

          <div className="taste-row">
            <strong>선호 배우</strong>
            <div className="taste-tags">
              {preferences.actors.length > 0 ? (
                preferences.actors.slice(0, 3).map((actor) => (
                  <span key={actor}>{actor}</span>
                ))
              ) : (
                <em className="taste-empty">분석 전</em>
              )}
            </div>
          </div>

          <div className="taste-row">
            <strong>관심 키워드</strong>
            <div className="taste-tags">
              {preferences.keywords.length > 0 ? (
                preferences.keywords.slice(0, 3).map((keyword) => (
                  <span key={keyword}>{getKeywordLabel(keyword, { compact: true, hashtag: true })}</span>
                ))
              ) : (
                <em className="taste-empty">분석 전</em>
              )}
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}

export default PreferenceCard;
