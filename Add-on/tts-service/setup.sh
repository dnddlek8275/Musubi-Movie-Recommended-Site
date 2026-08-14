#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ENV_DIR="$SCRIPT_DIR/.openvoice-env"
VENDOR_DIR="$SCRIPT_DIR/vendor"
OPENVOICE_DIR="$VENDOR_DIR/OpenVoice"
CONDA_BIN="${CONDA_BIN:-/opt/anaconda3/bin/conda}"

mkdir -p "$VENDOR_DIR" "$SCRIPT_DIR/references"

if [ ! -x "$ENV_DIR/bin/python" ]; then
  "$CONDA_BIN" create -y -p "$ENV_DIR" python=3.9
fi

# macOS에서 OpenVoice의 PyAV 10을 빌드/실행하는 네이티브 의존성.
# 설치된 환경을 매번 다시 해석하면 일부 Apple Silicon Conda에서 충돌할 수 있다.
if ! "$ENV_DIR/bin/python" -c "import av" >/dev/null 2>&1 || \
   [ ! -x "$ENV_DIR/bin/ffmpeg" ]; then
  "$CONDA_BIN" install -y -p "$ENV_DIR" -c conda-forge \
    "av=10" ffmpeg pkg-config
fi

if [ ! -d "$OPENVOICE_DIR/.git" ]; then
  git clone --depth 1 https://github.com/myshell-ai/OpenVoice.git "$OPENVOICE_DIR"
fi

"$ENV_DIR/bin/pip" install -e "$OPENVOICE_DIR"
"$ENV_DIR/bin/pip" install git+https://github.com/myshell-ai/MeloTTS.git
"$ENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
# macOS의 기본 대소문자 비구분 파일시스템에서는 mecab-python3의 `MeCab`과
# python-mecab-ko의 `mecab` 경로가 겹친다. KR 서비스가 사용할 한국어 바인딩을
# 마지막에 다시 설치하고, 앱에서는 사용하지 않는 일본어 모듈 import를 우회한다.
"$ENV_DIR/bin/pip" install --force-reinstall --no-deps python-mecab-ko==1.3.7
# 전체 UniDic(일본어용)는 받지 않는다. 앱이 KR 실행에 충분한 unidic_lite를
# 명시적으로 선택하므로 수백 MB의 일본어 사전 다운로드가 필요 없다.

if [ ! -f "$OPENVOICE_DIR/checkpoints_v2/converter/checkpoint.pth" ]; then
  # 공식 문서의 기존 S3 zip 링크가 간헐적으로 AccessDenied를 반환하므로,
  # MyShell 공식 Hugging Face 모델 저장소에서 동일한 V2 체크포인트를 받는다.
  "$ENV_DIR/bin/huggingface-cli" download myshell-ai/OpenVoiceV2 \
    --local-dir "$OPENVOICE_DIR/checkpoints_v2" \
    --local-dir-use-symlinks False
fi

echo "OpenVoice V2 setup complete. Run: $SCRIPT_DIR/start.sh"
