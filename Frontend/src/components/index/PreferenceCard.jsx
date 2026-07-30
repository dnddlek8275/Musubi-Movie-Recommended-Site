import { useEffect, useState } from 'react';

import { fetchUserPreferences } from '../../api.js';

function PreferenceCard({ authUser }) {
  const [nickname, setNickname] = useState(authUser?.nickname || '');
  const [preferences, setPreferences] = useState({
    genres: [],
    actors: [],
    keywords: [],
  });

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
      setPreferences({ genres: [], actors: [], keywords: [] });
      return undefined;
    }

    const controller = new AbortController();

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
            display: flex;
            align-items: flex-start;
            gap: 16px;
          }

          .taste-row strong {
            flex: 0 0 64px;
            padding-top: 5px;
            font-size: 16px;
            font-weight: 800;
            color: var(--text);
            white-space: nowrap;
          }

          .taste-tags {
            flex: 1;
            min-width: 0;
            max-height: 52px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            overflow: hidden;
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
            width: 315px;
            height: auto;
            margin: 0 0 0 155px;
            pointer-events: none;
            user-select: none;
          }

          .taste-card-mascot--light {
            display: none;
          }

          :root[data-theme="light"] .taste-card-mascot--dark {
            display: none;
          }

          :root[data-theme="light"] .taste-card-mascot--light {
            display: block;
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
            }
          }
        `}
      </style>

      <aside className="index-taste-card" aria-label="취향 분석">
        <a href="/chat/auto" className="taste-card-more">
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
          className="taste-card-mascot taste-card-mascot--dark"
          src="/images/ceneBuddy3.png"
          alt=""
          aria-hidden="true"
        />
        <img
          className="taste-card-mascot taste-card-mascot--light"
          src="/images/cinebuddy2.png"
          alt=""
          aria-hidden="true"
        />

        <div className="taste-card-preferences">
          <div className="taste-row">
            <strong>선호 장르</strong>
            <div className="taste-tags">
              {preferences.genres.length > 0 ? (
                preferences.genres.map((genre) => (
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
                preferences.actors.map((actor) => (
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
                preferences.keywords.map((keyword) => (
                  <span key={keyword}>{keyword}</span>
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
