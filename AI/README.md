# CineVerse AI

영화 캐릭터 대화와 영화 추천을 제공하는 RAG 기반 AI 서비스입니다. FastAPI API,
OpenAI 호환 로컬 LLM 서버, Milvus 벡터 데이터베이스를 사용합니다.

## 구성

- `api/`: FastAPI 애플리케이션
- `pipeline/`: 의도 분류, 질의 재작성, 캐릭터/영화 파이프라인
- `rag/`: 임베딩, 검색, 재정렬, 데이터 적재
- `eval/`: 검색 및 LLM 평가 스크립트
- `train/`: QLoRA 학습과 GGUF 내보내기 스크립트
- `docs/`: 기능 및 API 명세
- `test/`: 실험용 스크립트와 노트북

## 로컬 실행 준비

Python 가상환경을 만든 뒤 런타임 의존성을 설치합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

LLM 서버와 Milvus가 각각 기본 주소인 `http://localhost:8081`,
`http://localhost:19530`에서 실행 중이어야 합니다. LLM 주소와 모델명은
`.env`의 `LLM_BASE_URL`, `LLM_MODEL`, `LLM_TIMEOUT`으로 설정할 수 있습니다.

프로젝트 루트에서 API를 실행합니다.

```bash
uvicorn api.main:app --reload
```

엔드포인트와 요청/응답 형식은 [`docs/API_SPEC.md`](docs/API_SPEC.md)를
참고하세요.

## 학습

학습 의존성은 별도로 설치합니다.

```bash
pip install -r requirements-train.txt
```

학습 및 변환 스크립트에는 실행 환경에 맞는 데이터 경로와 모델 경로가
필요합니다. Hugging Face 인증이 필요한 경우 `.env` 또는 셸 환경에
`HF_TOKEN`을 설정하세요. 토큰은 저장소에 커밋하지 마세요.

## Git에 올리기 전

모델 가중치, 체크포인트, 로컬 환경파일은 `.gitignore`에서 제외됩니다.
큰 모델 파일을 반드시 버전 관리해야 한다면 일반 Git 대신 Git LFS 또는
외부 모델 저장소를 사용하세요.

