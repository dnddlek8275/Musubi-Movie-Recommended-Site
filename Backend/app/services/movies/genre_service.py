
# 장르 종류
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.movies import Movie, MovieGenre

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
        .where(MovieGenre.genre == genre)
        # 평점 높은 순으로 정렬 - 임시
        .order_by(Movie.vote_average.desc().nulls_last())
        .offset((page -1) * limit)
        .limit(limit)
    ).all()


    return genre_movies