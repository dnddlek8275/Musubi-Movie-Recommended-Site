from app.ai_client.base import post_ai

# ai - 날마다 추천하는 영화 리스트
async def request_recommend_today_movie(genre: str, movies: list[dict]):
    serialized_movies = []
    for movie in movies:
        release_date = movie.get("release_date")
        serialized_movies.append({
            **movie,
            "release_date": (
                release_date.isoformat()
                if hasattr(release_date, "isoformat")
                else release_date
            ),
        })
    payload = {
        "genre": genre,
        "movies": serialized_movies,
    }
    return await post_ai("/recommend/daily-copy", payload)

# 일반 영화 추천 기능
async def request_ai_recommend(payload : dict) -> dict:
    return await post_ai("/recommend", payload)
