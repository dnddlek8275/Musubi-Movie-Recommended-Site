import { useState } from 'react';

const GENRE_CARDS = [
  { name: '코미디', apiGenre: '코미디', image: '/images/genres/comedy.png' },
  { name: '액션', apiGenre: '액션', image: '/images/genres/action.png' },
  { name: '스릴러', apiGenre: '스릴러', image: '/images/genres/thriller.png' },
  { name: '애니메이션', apiGenre: '애니메이션', image: '/images/genres/animation.png' },
  { name: '드라마', apiGenre: '드라마', image: '/images/genres/drama.png' },
  { name: '공포', apiGenre: '공포', image: '/images/genres/horror.png' },
  { name: '멜로/로맨스', apiGenre: '로맨스', image: '/images/genres/romance.png' },
  { name: 'SF', apiGenre: 'SF', image: '/images/genres/sf.png' },
];

function pickRandomGenres(count) {
  const shuffledGenres = [...GENRE_CARDS];

  for (let index = shuffledGenres.length - 1; index > 0; index -= 1) {
    const randomIndex = Math.floor(Math.random() * (index + 1));
    [shuffledGenres[index], shuffledGenres[randomIndex]] = [
      shuffledGenres[randomIndex],
      shuffledGenres[index],
    ];
  }

  return shuffledGenres.slice(0, count);
}

function GenreSection() {
  // 페이지를 열 때 8개 장르 중 5개를 한 번만 골라, 렌더링 중 순서가 바뀌지 않게 한다.
  const [genres] = useState(() => pickRandomGenres(5));

  return (
    <section className="index-genre-section" aria-label="장르별 추천">
      <h2>장르별 추천</h2>

      <div className="index-genre-row">
        {genres.map((genre) => (
          <a
            className="index-genre-card"
            href={`/recommendations?genre=${encodeURIComponent(genre.apiGenre)}`}
            key={genre.name}
            style={{ backgroundImage: `url(${genre.image})` }}
            aria-label={`${genre.name} 장르 추천 영화 보기`}
          >
            <span>더보기 ›</span>
            <strong>{genre.name}</strong>
          </a>
        ))}
      </div>
    </section>
  );
}

export default GenreSection;
