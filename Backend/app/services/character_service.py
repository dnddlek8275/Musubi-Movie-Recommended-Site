from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.character import Character, CharacterAlias

# 채팅 가능한 캐릭터들 반환 함수
def characters_all_active(db : Session):
    # 캐릭터 테이블에서 is_active가 true인 캐릭터만 반환
    result = db.scalars(
        select(Character)
        .where(Character.is_active.is_(True))
        .order_by(Character.id.asc())
    ).all()

    return [
        {
            "id" : character.id,
            "name" : character.name,
            "movie_title" : character.movie_title,
            "profile_image" : character.profile_image,
        }
        for character in result
    ]

# 캐릭터 지금 가능 여부 확인 함수
def get_active_character(db : Session, character_name : str) :
    # 캐릭터 이름 앞뒤 공백 제거
    character_name = character_name.strip()

    if not character_name : return None

    character = db.scalar(select(Character)
        .where(Character.name == character_name, Character.is_active.is_(True))
    )

    # 없을 경우 별칭에도 있는지 확인
    if character is None :
        character_name = db.scalar(
            select(CharacterAlias)
            .where(CharacterAlias.alias == character_name)
        )
        if character_name is None: return None
        result = character_name.character.name
    else : result = character.name

    return result

# 그룹으로 받은 캐릭터들
def get_active_characters(db : Session, characters : list[str]):
    result = []

    # 캐릭터 하나씩 있는지 확인
    for character in characters:
        character = get_active_character(db, character)

        if character is None:
            return None
        
        result.append(character)
    
    return result
