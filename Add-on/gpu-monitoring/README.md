# NVIDIA GPU Monitoring Dashboard

GPU 서버의 NVML 메트릭을 FastAPI로 제공하고 React 대시보드에서 주기적으로 조회하는 모니터링 프로젝트입니다. 브라우저는 GPU에 직접 접근하지 않으며, 백엔드가 `nvidia-ml-py`를 통해 정보를 수집합니다. 실제 NVIDIA GPU가 없는 개발 환경에서는 Tesla T4 2대를 흉내 내는 목업 모드를 사용할 수 있습니다.

## 주요 기능

- GPU 사용률, 메모리 컨트롤러, VRAM, 온도, 전력, 팬, 클럭, 드라이버 정보
- Compute/Graphics GPU 프로세스와 `psutil` 기반 프로세스 이름·명령어
- GPU별 최근 60회 GPU/VRAM/온도/전력 Recharts 그래프
- 1·2·5·10초 자동 갱신, ON/OFF, 수동 갱신
- NVML/개별 기능 미지원, API 연결 끊김, 로딩 상태 구분
- 반응형 다크 대시보드와 접근 가능한 배지·프로그레스 바·표

## 구조와 기술 스택

```text
gpu-monitoring/
├── backend/
│   ├── app/{main.py,gpu_service.py,schemas.py,config.py}
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/api/gpuApi.js
│   ├── src/components/{GpuCard,UsageChart,ProcessTable,StatusBadge,ProgressBar}.jsx
│   ├── src/pages/DashboardPage.jsx
│   ├── src/{App.jsx,main.jsx,styles.css}
│   ├── package.json
│   ├── Dockerfile
│   └── .env.example
├── docker-compose.yml
├── .gitignore
└── README.md
```

백엔드는 Python, FastAPI, Uvicorn, Pydantic, nvidia-ml-py(NVML), psutil을 사용합니다. 프론트엔드는 React, Vite, JavaScript, Fetch API, Recharts와 일반 CSS를 사용합니다.

## 로컬 개발

### 1. 백엔드 (macOS/Linux)

```bash
cd gpu-monitoring/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
USE_MOCK_GPU_DATA=true uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

`.env` 파일은 Uvicorn이 자동으로 읽지 않습니다. 위처럼 셸 환경변수를 지정하거나 `uvicorn ... --env-file .env`를 사용하세요. 실제 GPU 서버에서는 `USE_MOCK_GPU_DATA=false`로 실행합니다.

### 2. 백엔드 (Windows PowerShell)

```powershell
cd gpu-monitoring\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
$env:USE_MOCK_GPU_DATA="true"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Windows 명령 프롬프트에서는 `.venv\Scripts\activate.bat`와 `set USE_MOCK_GPU_DATA=true`를 사용합니다.

### 3. 프론트엔드

별도 터미널에서 실행합니다.

```bash
cd gpu-monitoring/frontend
cp .env.example .env
npm install
npm run dev
```

- 대시보드: <http://localhost:5173>
- API 문서(Swagger): <http://localhost:8000/docs>
- 상태 확인: <http://localhost:8000/health>

## 환경변수

| 위치 | 변수 | 기본값 | 설명 |
| --- | --- | --- | --- |
| Backend | `USE_MOCK_GPU_DATA` | `false` | `true`이면 변동하는 Tesla T4 2대 데이터 반환 |
| Backend | `FRONTEND_ORIGIN` | `http://localhost:5173` | CORS 허용 Origin. 여러 주소는 쉼표로 구분 |
| Frontend | `VITE_API_BASE_URL` | `http://localhost:8000` | 브라우저가 호출할 공개 백엔드 URL |

Vite 환경변수는 빌드 시 주입됩니다. 값을 바꾼 뒤에는 개발 서버를 재시작하거나 Docker 이미지를 다시 빌드해야 합니다.

## API

- `GET /health`: 서버 동작 상태
- `GET /api/gpus`: 전체 GPU. NVML 미지원 시 HTTP 200과 `state: "unavailable"`, 빈 배열 반환
- `GET /api/gpus/{gpu_index}`: 특정 GPU. 범위 밖 인덱스는 HTTP 404
- `GET /api/gpus/{gpu_index}/processes`: 해당 GPU 프로세스. 범위 밖 인덱스는 HTTP 404

NVML이 특정 카드에서 팬 속도처럼 지원하지 않는 값을 요청해 오류를 내면, API 서버는 종료되지 않고 그 필드만 `null`로 반환합니다. 프로세스 정보는 권한이나 프로세스 종료 타이밍에 따라 이름과 명령어가 `null`일 수 있습니다.

## Docker

실제 GPU 접근에는 호스트의 NVIDIA 드라이버와 **NVIDIA Container Toolkit**이 필요합니다. 목업 모드에는 필요하지 않습니다.

### 방법 1: Docker Compose

GPU 서버에서:

```bash
cd gpu-monitoring
docker compose up --build
```

Compose의 `deploy.resources.reservations.devices`가 NVIDIA GPU를 예약합니다. Compose/Docker 버전이 이 문법을 지원하지 않거나 GPU가 없는 컴퓨터라면 GPU 예약 블록을 임시로 주석 처리한 뒤 목업 모드로 실행합니다.

```bash
USE_MOCK_GPU_DATA=true docker compose up --build
```

GPU 예약 설정은 Docker Compose 버전에 따라 `gpus: all`을 요구할 수 있습니다. `docker compose config`와 `docker compose version`으로 지원 여부를 확인하세요.

### 방법 2: 백엔드만 `docker run --gpus all`

Compose GPU 설정과 호환되지 않을 때 가장 명시적인 실행 방법입니다.

```bash
cd gpu-monitoring/backend
docker build -t gpu-monitor-backend .
docker run --rm --gpus all -p 8000:8000 \
  -e FRONTEND_ORIGIN=http://localhost:5173 \
  -e USE_MOCK_GPU_DATA=false \
  gpu-monitor-backend
```

그다음 프론트엔드는 로컬에서 `npm run dev`로 실행하거나 다음처럼 별도 컨테이너로 실행합니다.

```bash
cd gpu-monitoring/frontend
docker build --build-arg VITE_API_BASE_URL=http://localhost:8000 -t gpu-monitor-frontend .
docker run --rm -p 5173:80 gpu-monitor-frontend
```

## 자주 발생하는 오류

### `NVIDIA GPU or NVML is not available`

GPU가 없는 환경에서는 정상적인 `unavailable` 상태입니다. 화면 개발은 `USE_MOCK_GPU_DATA=true`로 진행합니다. GPU 서버라면 `nvidia-smi`가 호스트에서 동작하는지 확인하고 NVIDIA 드라이버를 점검하세요.

### 컨테이너에서 `Failed to initialize NVML` 또는 GPU가 보이지 않음

호스트에서 `nvidia-smi`를 먼저 확인하고 NVIDIA Container Toolkit을 설치·설정한 뒤 Docker 데몬을 재시작합니다. `docker run --rm --gpus all nvidia/cuda:12.5.0-base-ubuntu22.04 nvidia-smi`로 컨테이너 GPU 전달을 검증할 수 있습니다.

### 브라우저의 CORS 오류

프론트엔드 주소와 `FRONTEND_ORIGIN`이 프로토콜·호스트·포트까지 정확히 일치해야 합니다. 예를 들어 `localhost`와 `127.0.0.1`은 다른 Origin입니다. 둘 다 필요하면 쉼표로 지정합니다.

```bash
FRONTEND_ORIGIN=http://localhost:5173,http://127.0.0.1:5173 uvicorn app.main:app --reload
```

### 프로세스 이름/명령어가 비어 있음

다른 사용자의 프로세스를 읽을 권한이 없거나 조회 직전에 종료된 경우입니다. GPU 메모리 정보는 유지하고 접근할 수 없는 상세 필드만 `null`로 표시합니다. 필요한 경우 백엔드 실행 계정의 `/proc` 접근 권한을 확인하세요.

### 프론트엔드가 계속 연결 끊김으로 표시됨

`http://localhost:8000/health`와 `/api/gpus`를 직접 열어 백엔드를 확인합니다. 원격 서버에 배포했다면 `VITE_API_BASE_URL`을 브라우저에서 접근 가능한 주소로 설정하고 프론트엔드를 다시 빌드하세요. 컨테이너 내부 이름 `backend:8000`은 일반적으로 사용자의 브라우저에서 해석되지 않습니다.

## 전체 실행 순서

1. 실제 GPU를 쓸 경우 호스트의 `nvidia-smi`와 NVIDIA Container Toolkit을 확인합니다.
2. `backend`에서 가상환경을 만들고 `pip install -r requirements.txt`를 실행합니다.
3. GPU가 없으면 `USE_MOCK_GPU_DATA=true`, 있으면 `false`로 백엔드를 실행합니다.
4. `/health`, `/api/gpus`, `/docs`에서 API를 확인합니다.
5. `frontend`에서 `.env`의 `VITE_API_BASE_URL`을 확인하고 `npm install`, `npm run dev`를 실행합니다.
6. <http://localhost:5173>에서 카드, 그래프, 프로세스 표와 갱신 설정을 확인합니다.
7. 배포 시 `docker compose up --build` 또는 백엔드의 `docker run --gpus all` 방식을 선택합니다.
