import { useState } from 'react';

const HOME_SUGGESTIONS = [
  '오늘 기분에 어울리는 영화를 추천해줘',
  '가볍게 웃을 수 있는 코미디 영화를 골라줘',
  '혼자 보기 좋은 몰입감 높은 영화를 추천해줘',
  '비 오는 날 보기 좋은 영화를 알려줘',
  '잠들기 전에 편안하게 볼 영화를 추천해줘',
  '반전이 인상적인 스릴러 영화를 골라줘',
  '가족과 함께 보기 좋은 영화를 추천해줘',
  '연인과 보기 좋은 로맨스 영화를 알려줘',
  '꼭 봐야 할 한국 영화 명작을 추천해줘',
  '짧지만 강렬한 영화를 골라줘',
  '영상미가 아름다운 영화를 추천해줘',
  '음악이 좋은 영화를 찾아줘',
  '마음이 따뜻해지는 감동적인 영화를 추천해줘',
  '스트레스가 풀리는 시원한 액션 영화를 골라줘',
  '잘 알려지지 않은 숨은 명작을 추천해줘',
  '주말에 몰입해서 보기 좋은 영화를 알려줘',
];

const CHARACTER_SUGGESTIONS = [
  { label: '장첸과 긴장감 있는 대화 시작하기', value: '장첸' },
  { label: '마석도에게 고민 털어놓기', value: '마석도' },
  { label: '토니 스타크와 유쾌하게 이야기하기', value: '토니 스타크' },
  { label: '피터 파커와 편하게 수다 떨기', value: '피터 파커' },
  { label: '로키의 속마음 들어보기', value: '로키' },
  { label: '닥터 스트레인지에게 조언 구하기', value: '닥터 스트레인지' },
  { label: '브루스 웨인과 진지한 대화 나누기', value: '브루스 웨인' },
  { label: '조커와 예측할 수 없는 대화 시작하기', value: '조커' },
  { label: '헤르미온느에게 해결책 물어보기', value: '헤르미온느' },
  { label: '간달프에게 인생 조언 듣기', value: '간달프' },
  { label: '쿠퍼와 우주에 관해 이야기하기', value: '쿠퍼' },
  { label: '코브와 꿈에 관해 이야기하기', value: '코브' },
  { label: '존 윅과 짧고 강렬한 대화 시작하기', value: '존 윅' },
  { label: '잭 스패로우의 모험담 들어보기', value: '잭 스패로우' },
  { label: '엘사에게 마음속 이야기 들려주기', value: '엘사' },
  { label: '우디와 따뜻한 우정 이야기 나누기', value: '우디' },
];

function pickTwo(items) {
  const firstIndex = Math.floor(Math.random() * items.length);
  let secondIndex = Math.floor(Math.random() * (items.length - 1));
  if (secondIndex >= firstIndex) secondIndex += 1;
  return [items[firstIndex], items[secondIndex]];
}

function GuestChatNotice({
  showGuestMessage = false,
  hidden = false,
  mode = 'home',
  onSuggestionSelect,
  onGroupStart,
}) {
  const [suggestions] = useState(() => {
    const picked = pickTwo(mode === 'group' ? CHARACTER_SUGGESTIONS : HOME_SUGGESTIONS);
    return mode === 'group' ? picked.slice(0, 1) : picked;
  });

  return (
    <aside
      className={`guest-chat-simple-notice${hidden ? ' is-hidden' : ''}`}
      aria-label="대화 서비스 안내"
      aria-hidden={hidden}
    >
      {showGuestMessage ? (
        <p>비회원 서비스는 채팅이 10회로 제한됩니다. 로그인하고 더 많은 대화를 나눠보세요.</p>
      ) : null}
      <nav aria-label="대화 서비스 이동">
        {mode === 'group' ? (
          <a href="/home" tabIndex={hidden ? -1 : undefined}>
            <span aria-hidden="true">✦</span>
            무무에게 영화 추천받기
          </a>
        ) : (
          <a href="/chat/group" tabIndex={hidden ? -1 : undefined}>
            <span aria-hidden="true">✦</span>
            영화 속 캐릭터와 대화해보기
          </a>
        )}
        {mode === 'group' ? (
          <button
            type="button"
            tabIndex={hidden ? -1 : undefined}
            onClick={onGroupStart}
          >
            <span aria-hidden="true">✦</span>
            캐릭터와 단체 대화하기
          </button>
        ) : null}
      </nav>
      <div className="guest-chat-suggestions" aria-label="추천 질문">
        {suggestions.map((suggestion, index) => {
          const label = typeof suggestion === 'string' ? suggestion : suggestion.label;
          const value = typeof suggestion === 'string' ? suggestion : suggestion.value;
          return (
            <button
              type="button"
              key={`${label}-${index}`}
              tabIndex={hidden ? -1 : undefined}
              onClick={() => onSuggestionSelect?.(value)}
            >
              <span aria-hidden="true">✦</span>
              {label}
            </button>
          );
        })}
      </div>
    </aside>
  );
}

export default GuestChatNotice;
