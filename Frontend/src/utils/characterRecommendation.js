const CHARACTER_CHAT_STORAGE_KEY = 'cineverse.groupchat.conversations';

function normalizeValue(value) {
  const raw = typeof value === 'object' && value !== null
    ? value.value || value.name || value.label || ''
    : value || '';
  return String(raw).trim().replace(/^#/, '').toLocaleLowerCase('ko-KR');
}

function preferenceStrengthMap(values) {
  const entries = (Array.isArray(values) ? values : [])
    .map((entry) => ({
      value: normalizeValue(entry),
      score: typeof entry === 'object' && entry !== null && Number.isFinite(Number(entry.score))
        ? Math.max(Number(entry.score), 0)
        : null,
    }))
    .filter((entry) => entry.value);

  const maximumScore = Math.max(
    0,
    ...entries.map((entry) => entry.score ?? 0),
  );
  const strengths = new Map();

  entries.forEach((entry) => {
    const strength = entry.score === null || maximumScore <= 0
      ? 1
      : entry.score / maximumScore;
    strengths.set(entry.value, Math.max(strengths.get(entry.value) || 0, strength));
  });

  return strengths;
}

function categoryMatchScore(values, strengths) {
  const normalizedValues = (Array.isArray(values) ? values : [values])
    .map(normalizeValue)
    .filter(Boolean);
  return Math.min(
    1,
    normalizedValues.reduce((total, value) => total + (strengths.get(value) || 0), 0),
  );
}

function readRecentCharacterNames() {
  try {
    const stored = JSON.parse(window.localStorage.getItem(CHARACTER_CHAT_STORAGE_KEY) || '{}');
    const conversations = Array.isArray(stored) ? stored : stored?.conversations;
    const recentNames = [];

    (Array.isArray(conversations) ? conversations : [])
      .slice()
      .sort((left, right) => (
        new Date(right?.updatedAt || right?.createdAt || 0).getTime()
        - new Date(left?.updatedAt || left?.createdAt || 0).getTime()
      ))
      .forEach((conversation) => {
        (conversation?.members || []).forEach((member) => {
          const name = normalizeValue(member?.name || member);
          if (name && !recentNames.includes(name)) recentNames.push(name);
        });
      });

    return recentNames.slice(0, 5);
  } catch {
    return [];
  }
}

function stableHash(value) {
  let hash = 2166136261;
  for (const character of String(value)) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

/**
 * 캐릭터 추천 공통 점수
 * - 장르 50%, 키워드 30%, 배우 20%
 * - 최근 대화한 캐릭터는 최대 6점의 약한 중복 감점
 * - 동점은 하루 동안 고정되는 순서로 순환
 */
export function rankCharactersForRecommendation(characters, preferences, { limit = 0 } = {}) {
  const genreStrengths = preferenceStrengthMap(preferences?.genres);
  const keywordStrengths = preferenceStrengthMap(preferences?.keywords);
  const actorStrengths = preferenceStrengthMap(preferences?.actors);
  const recentNames = readRecentCharacterNames();
  const dayKey = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Seoul' });

  const ranked = (Array.isArray(characters) ? characters : [])
    .map((character, index) => {
      const recentIndex = recentNames.indexOf(normalizeValue(character?.name));
      const recentPenalty = recentIndex >= 0 ? 6 / (recentIndex + 1) : 0;
      const score = (
        categoryMatchScore(character?.genres, genreStrengths) * 50
        + categoryMatchScore(character?.keywords, keywordStrengths) * 30
        + categoryMatchScore(character?.actor || character?.actors, actorStrengths) * 20
        - recentPenalty
      );

      return {
        character,
        index,
        score,
        tieOrder: stableHash(`${dayKey}:${character?.id ?? character?.name ?? index}`),
      };
    })
    .sort((left, right) => (
      right.score - left.score
      || left.tieOrder - right.tieOrder
      || left.index - right.index
    ))
    .map(({ character }) => character);

  return limit > 0 ? ranked.slice(0, limit) : ranked;
}
