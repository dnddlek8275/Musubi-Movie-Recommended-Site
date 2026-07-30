
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.actors import Actor

# 배우 조회
def get_actors_result(db : Session):
    actors = []
    actors = db.scalars(select(Actor)).all()
    return actors
