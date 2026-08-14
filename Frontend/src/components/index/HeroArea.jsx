import CharacterChatPanel from './CharacterChatPanel.jsx';
import PreferenceCard from './PreferenceCard.jsx';
import PromoBanner from './PromoBanner.jsx';

function HeroArea({ authUser, characterStart, onNextCharacters, visibleCharacters }) {
  return (
    <section className="index-hero-grid" aria-label="메인 추천 영역">
      <div className="index-hero-left">
        <PromoBanner />

        <CharacterChatPanel
          characterStart={characterStart}
          onNextCharacters={onNextCharacters}
          visibleCharacters={visibleCharacters}
        />
      </div>

      <PreferenceCard authUser={authUser} />
    </section>
  );
}

export default HeroArea;
