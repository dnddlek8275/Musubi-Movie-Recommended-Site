import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import types
import importlib.util
from functools import lru_cache
from pathlib import Path
from typing import Optional

# 모델 캐시는 서비스 폴더 안에 둔다. MeloTTS가 import 시점에 다국어
# 토크나이저를 초기화하므로 관련 import보다 먼저 설정해야 한다.
MODULE_ROOT = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(MODULE_ROOT / ".cache" / "huggingface"))
os.environ.setdefault("TRANSFORMERS_CACHE", str(MODULE_ROOT / ".cache" / "transformers"))
os.environ.setdefault("NLTK_DATA", str(MODULE_ROOT / ".cache" / "nltk_data"))

import torch
import unidic_lite
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
# MeloTTS는 선택 언어와 무관하게 일본어 모듈도 즉시 import한다. 대소문자를
# 구분하지 않는 macOS에서는 일본어 `MeCab`과 한국어 `mecab` 패키지가 같은 경로로
# 충돌하므로, KR 전용 서비스에서는 사용하지 않는 일본어 모듈만 지연 스텁 처리한다.
sys.modules["unidic"] = unidic_lite
mecab_dir = Path(unidic_lite.__file__).resolve().parent.parent / "MeCab"
mecab_spec = importlib.util.spec_from_file_location(
    "mecab",
    mecab_dir / "__init__.py",
    submodule_search_locations=[str(mecab_dir)],
)
if mecab_spec is None or mecab_spec.loader is None:
    raise ImportError(f"Korean MeCab package not found: {mecab_dir}")
korean_mecab = importlib.util.module_from_spec(mecab_spec)
sys.modules["mecab"] = korean_mecab
mecab_spec.loader.exec_module(korean_mecab)
japanese_stub = types.ModuleType("melo.text.japanese")
japanese_stub.text_normalize = lambda text: text
japanese_stub.distribute_phone = lambda n_phone, n_word: [
    n_phone // n_word + (1 if index < n_phone % n_word else 0)
    for index in range(n_word)
]
japanese_stub.g2p = lambda _text: (_ for _ in ()).throw(
    RuntimeError("Japanese synthesis is disabled in this Korean TTS service")
)
japanese_stub.get_bert_feature = japanese_stub.g2p
sys.modules["melo.text.japanese"] = japanese_stub

from melo.api import TTS
from openvoice import se_extractor
from openvoice.api import ToneColorConverter
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask


ROOT = MODULE_ROOT
OPENVOICE_DIR = Path(os.getenv("OPENVOICE_DIR", ROOT / "vendor" / "OpenVoice"))
CHECKPOINT_DIR = Path(
    os.getenv("OPENVOICE_CHECKPOINT_DIR", OPENVOICE_DIR / "checkpoints_v2")
)
REFERENCE_DIR = Path(os.getenv("OPENVOICE_REFERENCE_DIR", ROOT / "references"))
DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
VOICE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9가-힣_-]{1,100}$")
ENGLISH_PATTERN = re.compile(r"[A-Za-z]")
KOREAN_PATTERN = re.compile(r"[가-힣]")
MODEL_LOCK = threading.Lock()
CHATAI_PRESET = "chatai"

app = FastAPI(title="Musubi OpenVoice V2 TTS", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "TTS_ALLOWED_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    ).split(",") if origin.strip()],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    character: str = Field(default="AI", max_length=100)
    # references/<voice>.wav 또는 .mp3가 있으면 해당 음색을 복제한다.
    voice: str = Field(default=CHATAI_PRESET, max_length=100)
    rate: float = Field(default=1.0, ge=0.6, le=2.0)
    # AUTO는 입력 문자의 비율로 KR/EN을 선택한다.
    language: str = Field(default="AUTO", max_length=10)


def detect_language(text: str, requested_language: str = "AUTO") -> str:
    language = requested_language.strip().upper()
    aliases = {
        "AUTO": "AUTO",
        "KR": "KR",
        "KO": "KR",
        "KO-KR": "KR",
        "KOREAN": "KR",
        "EN": "EN",
        "EN-US": "EN",
        "EN-GB": "EN",
        "ENGLISH": "EN",
    }
    language = aliases.get(language, language)
    if language not in {"AUTO", "KR", "EN"}:
        raise HTTPException(
            status_code=400,
            detail="language must be AUTO, KR, or EN",
        )
    if language != "AUTO":
        return language

    english_count = len(ENGLISH_PATTERN.findall(text))
    korean_count = len(KOREAN_PATTERN.findall(text))
    return "EN" if english_count > korean_count else "KR"


def normalize_english_text(text: str) -> str:
    replacements = {
        "²": " squared ",
        "³": " cubed ",
        "=": " equals ",
        "+": " plus ",
        "−": " minus ",
        "–": " minus ",
        "—": " minus ",
        "×": " times ",
        "÷": " divided by ",
        "%": " percent ",
        "&": " and ",
        "@": " at ",
    }
    for symbol, spoken in replacements.items():
        text = text.replace(symbol, spoken)
    return " ".join(text.split())


@lru_cache(maxsize=2)
def get_models(language: str):
    converter_dir = CHECKPOINT_DIR / "converter"
    config_path = converter_dir / "config.json"
    checkpoint_path = converter_dir / "checkpoint.pth"
    if not config_path.exists() or not checkpoint_path.exists():
        raise FileNotFoundError(
            f"OpenVoice V2 checkpoints not found: {CHECKPOINT_DIR}. Run ./setup.sh."
        )

    converter = ToneColorConverter(str(config_path), device=DEVICE)
    converter.load_ckpt(str(checkpoint_path))
    base_tts = TTS(language=language, device=DEVICE)
    speaker_key, speaker_id = next(iter(base_tts.hps.data.spk2id.items()))
    source_key = speaker_key.lower().replace("_", "-")
    source_se_path = CHECKPOINT_DIR / "base_speakers" / "ses" / f"{source_key}.pth"
    if not source_se_path.exists():
        raise FileNotFoundError(f"Base speaker embedding not found: {source_se_path}")
    source_se = torch.load(source_se_path, map_location=DEVICE)
    return converter, base_tts, speaker_id, source_se


def find_reference(voice: str) -> Optional[Path]:
    if not VOICE_NAME_PATTERN.fullmatch(voice):
        raise HTTPException(status_code=400, detail="Invalid voice name")
    for suffix in (".wav", ".mp3", ".m4a", ".flac"):
        candidate = REFERENCE_DIR / f"{voice}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def installed_voices() -> list[dict]:
    if not REFERENCE_DIR.exists():
        return []
    return [
        {"name": path.stem, "reference": path.name, "cloning": True}
        for path in sorted(REFERENCE_DIR.iterdir())
        if path.is_file() and path.suffix.lower() in {".wav", ".mp3", ".m4a", ".flac"}
    ]


def apply_chatai_style(input_path: Path, output_path: Path) -> None:
    """Create an original bright upper-elementary-age synthetic voice."""
    # Raise pitch by four semitones while preserving duration, remove excessive
    # lows, and emphasize consonant clarity. This does not clone a real child.
    pitch_ratio = 2 ** (4 / 12)
    filter_chain = (
        f"asetrate=44100*{pitch_ratio:.8f},"
        "aresample=44100,"
        f"atempo={1 / pitch_ratio:.8f},"
        "highpass=f=95,"
        "equalizer=f=220:t=q:w=1.0:g=-2,"
        "equalizer=f=2800:t=q:w=1.1:g=2.5,"
        "lowpass=f=10500,"
        "acompressor=threshold=-20dB:ratio=2.2:attack=8:release=120:makeup=1.5dB,"
        "alimiter=limit=0.94"
    )
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(input_path), "-af", filter_chain, str(output_path),
        ],
        check=True,
    )


@app.get("/health")
def health():
    ready = (CHECKPOINT_DIR / "converter" / "checkpoint.pth").exists()
    return {
        "status": "ok" if ready else "model_missing",
        "engine": "OpenVoice V2",
        "device": DEVICE,
        "checkpoint_dir": str(CHECKPOINT_DIR),
        "voices": installed_voices(),
    }


@app.get("/voices")
def voices():
    return {
        "presets": [{
            "name": CHATAI_PRESET,
            "languages": ["ko-KR", "en-US"],
            "cloning": False,
            "style": "bright, clear, upper-elementary-age synthetic voice",
        }],
        "cloned": installed_voices(),
    }


@app.post("/synthesize")
def synthesize(request: SynthesisRequest):
    reference_path = find_reference(request.voice)
    work_dir = Path(tempfile.mkdtemp(prefix="cineverse-openvoice-"))
    base_path = work_dir / "base.wav"
    output_path = work_dir / "output.wav"
    styled_path = work_dir / "styled.wav"
    chatai_style = request.voice == CHATAI_PRESET
    language = detect_language(request.text, request.language)
    synthesis_text = (
        normalize_english_text(request.text)
        if language == "EN"
        else request.text
    )

    try:
        with MODEL_LOCK:
            converter, base_tts, speaker_id, source_se = get_models(language)
            base_tts.tts_to_file(
                synthesis_text,
                speaker_id,
                str(base_path),
                speed=request.rate * (1.06 if chatai_style else 1.0),
            )

            if reference_path is None:
                shutil.move(base_path, output_path)
            else:
                target_se, _ = se_extractor.get_se(
                    str(reference_path), converter, vad=True
                )
                converter.convert(
                    audio_src_path=str(base_path),
                    src_se=source_se,
                    tgt_se=target_se,
                    output_path=str(output_path),
                    message="@Musubi",
                )

            if chatai_style:
                apply_chatai_style(output_path, styled_path)
                shutil.move(styled_path, output_path)
    except FileNotFoundError as error:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"OpenVoice synthesis failed: {error}") from error

    return FileResponse(
        output_path,
        media_type="audio/wav",
        filename="speech.wav",
        background=BackgroundTask(shutil.rmtree, work_dir, ignore_errors=True),
        headers={"Cache-Control": "no-store"},
    )
