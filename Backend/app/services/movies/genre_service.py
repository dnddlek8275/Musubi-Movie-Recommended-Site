
# 장르 종류
from sqlalchemy import func, select
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
    normalized_genre = str(genre or "").strip().casefold()
    # 장르 관련 영화
    statement = (
        select(Movie)
        .join(MovieGenre, Movie.id == MovieGenre.movie_id)
        .join(
            MovieGenreWeight,
            (MovieGenreWeight.movie_id == Movie.id)
            # 가중치 장르명은 casefold된 값으로 저장된다. 표시용 장르명
            # "SF"와 가중치 키 "sf"도 같은 장르로 조인해야 한다.
            & (
                MovieGenreWeight.genre
                == func.lower(func.btrim(MovieGenre.genre))
            ),
        )
        .where(func.lower(func.btrim(MovieGenre.genre)) == normalized_genre)
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


def country_movies(
        db: Session,
        country_code: str,
        page: int = 1,
        limit: int = 20,
):
    normalized_country_code = str(country_code or "").strip().upper()
    statement = (
        select(Movie)
        .where(Movie.production_countries.op("&&")([normalized_country_code]))
        .order_by(
            Movie.release_date.desc().nulls_last(),
            Movie.year.desc().nulls_last(),
            Movie.id.desc(),
        )
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return db.scalars(statement).all()
