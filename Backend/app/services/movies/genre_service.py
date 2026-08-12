
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
        sort: str = "relevance",
) :
    # 장르 관련 영화
    statement = (
        select(Movie)
        .join(MovieGenre, Movie.id == MovieGenre.movie_id)
        .join(
            MovieGenreWeight,
            (MovieGenreWeight.movie_id == Movie.id)
            & (MovieGenreWeight.genre == MovieGenre.genre),
        )
        .where(MovieGenre.genre == genre)
        .where(MovieGenreWeight.weight >= GENRE_RELEVANCE_MINIMUM)
    )
    if sort == "latest":
        statement = statement.order_by(
            Movie.release_date.desc().nulls_last(),
            Movie.year.desc().nulls_last(),
            Movie.id.desc(),
        )
    else:
        statement = statement.order_by(
            MovieGenreWeight.weight.desc(),
            Movie.vote_count.desc().nulls_last(),
            Movie.vote_average.desc().nulls_last(),
        )

    genre_movies = db.scalars(
        statement
        .offset((page -1) * limit)
        .limit(limit)
    ).all()


    return genre_movies
