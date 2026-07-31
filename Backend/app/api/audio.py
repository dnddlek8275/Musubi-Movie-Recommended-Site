import os
import tempfile

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from app.core.current_user import get_current_user
from app.core.api_responses import error_response
from app.core.dependencies import get_db
from app.services.speech_to_text_service import transcribe_audio
from app.services.stt_term_correction_service import build_character_hotwords, correct_stt_terms


router = APIRouter(
    prefix="/audio",
    tags=["Audio"],
    dependencies=[Depends(get_current_user)],
)

MAX_AUDIO_SIZE = 20 * 1024 * 1024

ALLOWED_AUDIO_TYPES = {
    "audio/webm": ".webm",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/ogg": ".ogg",
}


# 프론트 음성을 텍스트로 변환하고 DB의 영화·인물·장르를 기준으로 보정한다.
@router.post("/transcribe")
async def transcribe_uploaded_audio(
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    temp_audio_path = None

    try:
        content_type = (audio.content_type or "").split(";")[0].strip().lower()
        file_suffix = ALLOWED_AUDIO_TYPES.get(content_type)

        if file_suffix is None:
            return {
                "state": "failure",
                "message": "지원하지 않는 음성 파일 형식입니다.",
                "data": {
                    "allowed_types": list(ALLOWED_AUDIO_TYPES.keys()),
                },
            }

        audio_contents = await audio.read(MAX_AUDIO_SIZE + 1)

        if not audio_contents:
            return {
                "state": "failure",
                "message": "업로드된 음성 파일이 비어 있습니다.",
            }

        if len(audio_contents) > MAX_AUDIO_SIZE:
            return {
                "state": "failure",
                "message": "음성 파일은 최대 20MB까지 업로드할 수 있습니다.",
            }

        # Whisper가 읽을 수 있도록 음성을 서버 임시 파일로 저장한다.
        with tempfile.NamedTemporaryFile(suffix=file_suffix, delete=False) as temp_audio:
            temp_audio.write(audio_contents)
            temp_audio_path = temp_audio.name

        # 활성 캐릭터 공식 이름만 Whisper 힌트로 사용하고 별칭은 인식 후 보정한다.
        character_hotwords = build_character_hotwords(db)

        # CPU 기반 음성 인식이 다른 비동기 요청을 막지 않도록 별도 스레드에서 실행한다.
        recognized_text = await run_in_threadpool(
            transcribe_audio,
            temp_audio_path,
            character_hotwords,
        )

        if not recognized_text:
            return {
                "state": "failure",
                "message": "음성을 정확하게 인식하지 못했습니다. 다시 말씀해 주세요.",
            }

        # Whisper 원문에서 확실하게 유사한 영화·인물·장르 표현만 정상 표기로 바꾼다.
        corrected_text = correct_stt_terms(
            db=db,
            text=recognized_text,
        )

        return {
            "state": "success",
            "message": "음성을 텍스트로 변환했습니다.",
            "data": {
                "text": corrected_text,
            },
        }

    except Exception:
        return error_response("음성 변환 중 에러가 발생했습니다.")

    finally:
        await audio.close()

        # 음성 원본을 보관하지 않도록 변환에 사용한 임시 파일을 즉시 삭제한다.
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
