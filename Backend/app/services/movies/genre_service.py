
# 장르 종류
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.movies import Movie, MovieGenre, MovieGenreWeight
from app.services.movies.genre_relevance import GENRE_RELEVANCE_MINIMUM

def genre_movies (
        db: Session, 
        genre:str,
        page : int = 1,
        limit : int = 20,
) :
    # 장르 관련 영화
    genre_movies = db.scalars(
        select(Movie)
        .join(MovieGenre, Movie.id == MovieGenre.movie_id)
        .join(
            MovieGenreWeight,
            (MovieGenreWeight.movie_id == Movie.id)
            & (MovieGenreWeight.genre == MovieGenre.genre),
        )
        .where(MovieGenre.genre == genre)
        .where(MovieGenreWeight.weight >= GENRE_RELEVANCE_MINIMUM)
        .order_by(
            MovieGenreWeight.weight.desc(),
            Movie.vote_count.desc().nulls_last(),
            Movie.vote_average.desc().nulls_last(),
        )
        .offset((page -1) * limit)
        .limit(limit)
    ).all()


    return genre_movies
