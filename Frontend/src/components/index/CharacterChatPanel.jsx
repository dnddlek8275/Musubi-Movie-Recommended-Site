import CharacterAvatar from './CharacterAvatar.jsx';
import { VISIBLE_CHARACTER_COUNT } from './constants.js';

function CharacterChatPanel({ visibleCharacters, onNextCharacters }) {
  // 캐릭터를 아직 못 받아왔을 때도 자리(테두리)만이라도 보이게 채워둠
  const items =
    visibleCharacters.length > 0
      ? visibleCharacters
      : Array.from({ length: VISIBLE_CHARACTER_COUNT }, () => null);

  return (
    <section className="index-character-panel" aria-label="영화 속 캐릭터">
      <h2>영화속 캐릭터와 대화하기</h2>

      <div className="index-character-strip">
        <div className="index-character-list">
          {items.map((character, index) => (
            <CharacterAvatar
              key={character?.id || character?.name || `placeholder-${index}`}
              character={character}
              index={index}
            />
          ))}
        </div>

        <button
          className="index-character-next"
          type="button"
          onClick={onNextCharacters}
          aria-label="다음 캐릭터 보기"
        >
          ›
        </button>
      </div>
    </section>
  );
}

export default CharacterChatPanel;