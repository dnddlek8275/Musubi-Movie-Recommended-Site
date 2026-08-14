from functools import lru_cache

from faster_whisper import WhisperModel


MAX_NO_SPEECH_PROBABILITY = 0.50
MIN_AVERAGE_LOG_PROBABILITY = -0.80
MAX_COMPRESSION_RATIO = 2.40
MIN_RECOGNIZED_SPEECH_SECONDS = 0.50


# 첫 STT 요청에서 Whisper 모델을 불러온 뒤 서버 프로세스 안에서 재사용한다.
@lru_cache(maxsize=1)
def get_stt_model() -> WhisperModel:
    return WhisperModel(
        "small",
        device="cpu",
        compute_type="int8",
    )


# DB의 캐릭터 이름을 참고해 신뢰도가 충분한 한국어 발화만 문자열로 변환한다.
def transcribe_audio(
    audio_path: str,
    hotwords: str | None = None,
) -> str:
    model = get_stt_model()
    segments, _ = model.transcribe(
        audio_path,
        language="ko",
        # 문장 후보를 최대 5개씩 비교하여 가장 가능성이 높은 결과를 선택한다.
        beam_size=5,
        # 사람이 실제로 말하는 구간만 찾아 음성 인식에 사용한다.
        vad_filter=True,
        vad_parameters={
            "threshold": 0.50,
            "min_speech_duration_ms": 300,
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 200,
        },
        # 활성 캐릭터 이름이 일반 단어보다 고유명사 후보로 선택될 가능성을 높인다.
        hotwords=hotwords,
        # 앞 구간의 잘못된 문장이 다음 구간에 반복되는 현상을 줄인다.
        condition_on_previous_text=False,
        # 긴 무음 구간에서 실제로 말하지 않은 문장이 생성되는 현상을 줄인다.
        hallucination_silence_threshold=1.0,
        no_speech_threshold=0.60,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.40,
    )

    recognized_texts = []
    recognized_speech_seconds = 0.0

    for segment in segments:
        # 음성이 없거나 인식 신뢰도가 낮은 구간은 채팅 문장에 포함하지 않는다.
        if segment.no_speech_prob >= MAX_NO_SPEECH_PROBABILITY:
            continue

        if segment.avg_logprob < MIN_AVERAGE_LOG_PROBABILITY:
            continue

        if segment.compression_ratio > MAX_COMPRESSION_RATIO:
            continue

        segment_text = segment.text.strip()

        if segment_text:
            recognized_texts.append(segment_text)
            recognized_speech_seconds += max(
                segment.end - segment.start,
                0.0,
            )

    # 유효한 발화가 너무 짧으면 추측 문장을 보내지 않고 인식 실패로 처리한다.
    if recognized_speech_seconds < MIN_RECOGNIZED_SPEECH_SECONDS:
        return ""

    return " ".join(recognized_texts)
