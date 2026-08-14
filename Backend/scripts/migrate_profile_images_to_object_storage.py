"""기존 로컬 프로필 이미지를 Object Storage로 이전한다.

기본 실행은 조회만 수행한다. 실제 업로드와 DB 변경은 --apply가 필요하다.
"""

from __future__ import annotations

import argparse
import mimetypes
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.core.config import settings
from app.core.dependencies import SessionLocal
from app.models.users import User
from app.services.object_storage_service import upload_object
from app.services.user_service import get_profile_image_path


def migrate(*, apply_changes: bool) -> tuple[int, int]:
    migrated = 0
    skipped = 0
    db = SessionLocal()
    try:
        users = db.scalars(
            select(User).where(User.profile_image.like("/uploads/%"))
        ).all()

        for user in users:
            local_path = get_profile_image_path(user.profile_image)
            if not local_path or not local_path.is_file():
                print(f"SKIP user_id={user.id}: local file not found")
                skipped += 1
                continue

            extension = Path(local_path).suffix.lower()
            object_name = f"profile_{uuid4().hex}{extension}"
            object_key = (
                f"{settings.OBJECT_STORAGE_PROFILE_PREFIX.strip('/')}"
                f"/{user.id}/{object_name}"
            )
            print(f"PLAN user_id={user.id}: {local_path} -> {object_key}")

            if not apply_changes:
                continue

            content_type = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
            object_uri = upload_object(
                key=object_key,
                contents=local_path.read_bytes(),
                content_type=content_type,
            )
            user.profile_image = object_uri
            db.commit()
            migrated += 1

        return migrated, skipped
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="실제 Object Storage 업로드와 DB 갱신을 수행합니다.",
    )
    args = parser.parse_args()
    migrated, skipped = migrate(apply_changes=args.apply)
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"{mode} complete: migrated={migrated}, skipped={skipped}")


if __name__ == "__main__":
    main()
