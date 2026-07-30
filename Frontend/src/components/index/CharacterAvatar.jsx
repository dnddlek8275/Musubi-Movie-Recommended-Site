import { VISIBLE_CHARACTER_COUNT } from './constants.js';

function CharacterAvatar({ character, index }) {
  const spriteClass = `index-character__sprite character-sprite--${
    (index % VISIBLE_CHARACTER_COUNT) + 1
  }`;

  // 캐릭터를 아직 못 받아왔을 때: 깨진 이미지 아이콘 대신 테두리만 있는 빈 원을 보여줌
  if (!character) {
    return (
      <article className="index-character">
        <div className={spriteClass} aria-hidden="true" />
        <span>&nbsp;</span>
      </article>
    );
  }

  const imageUrl =
    character.img ||
    character.imageUrl ||
    character.image_url ||
    character.image ||
    '';

  // 캐릭터를 클릭하면 1:1 대화창(/chat)으로 이동하면서, 어떤 캐릭터와
  // 바로 대화를 시작할지 쿼리로 넘겨준다.
  const params = new URLSearchParams();
  if (character.id) params.set('characterId', String(character.id));
  if (character.name) params.set('characterName', character.name);
  const chatHref = `/chat?${params.toString()}`;

  return (
    <a
      className="index-character"
      href={chatHref}
      aria-label={`${character.name}와(과) 대화하기`}
    >
      {imageUrl ? (
        // 뒤에 같은 이미지를 확대·블러로 깔아, 원본 비율로 인해 생기는 빈 부분을
        // 이미지 바깥쪽 색이 이어지도록 채운다.
        <span
          className="index-character__avatar"
          style={{ '--char-img': `url("${imageUrl}")` }}
        >
          <img
            className={spriteClass}
            src={imageUrl}
            alt={`${character.name} 이미지`}
          />
        </span>
      ) : (
        <div className={spriteClass} aria-label={`${character.name} 이미지`} />
      )}

      <span>{character.name}</span>
    </a>
  );
}

export default CharacterAvatar;
