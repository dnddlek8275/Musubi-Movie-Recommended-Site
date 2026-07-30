import random

from app.ai_client.base import post_ai
from app.schemas.movies import RecommendRequest

genre_list= ["액션", "드라마", "코미디", "로맨스", "스릴러", "공포", "SF", "판타지", "범죄", "애니메이션"]
# ai - 날마다 추천하는 영화 리스트
async def request_recommend_today_movie():

    select_genre = random.choice(genre_list)

    payload = {
        "message": (
                f"메인 페이지에 보여줄 {select_genre}중에 랜덤으로 영화 추천 리스트를 만들어줘. "
                "answer는 오늘 하루에 어울리는 목록 전체의 분위기를 소개하는 짧은 감성 문구로 작성해줘. "
                "answer에 특정 영화 제목을 넣지 말고, 영화별 줄거리 설명도 하지 마. "
                "answer는 반드시 1문장, 45자 이내로 작성해줘."
            ),
        "history" : [],
    }
    
    return await post_ai("/recommend", payload)

# 일반 영화 추천 기능
async def request_ai_recommend(payload : dict) -> dict:
    return await post_ai("/recommend", payload)