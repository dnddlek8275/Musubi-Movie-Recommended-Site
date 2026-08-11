# Musubi AI

영화 캐릭터 대화와 영화 추천을 제공하는 RAG 기반 AI 서비스입니다. FastAPI API,
OpenAI 호환 로컬 LLM 서버, Milvus 벡터 데이터베이스를 사용합니다.

## 구성

- `api/`: FastAPI 애플리케이션
- `pipeline/`: 의도 분류, 질의 재작성, 캐릭터/영화 파이프라인
- `services/`: 월간 한도와 캐시를 포함한 외부 웹 검색 연동
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

## 선택 기능: 외부 웹 검색

`TAVILY_API_KEY`를 설정하면 사용자가 웹 검색을 명시적으로 요청한 경우에만
Tavily 결과를 로컬 LLM에 전달합니다. 기본 설정은 월 950회 하드 캡, 900회 경고,
동일 검색어 6시간 캐시입니다. 키가 없으면 기존 대화와 영화 추천만 동작합니다.
실제 키는 `.env` 또는 서비스 비밀 환경에만 두고 저장소에는 올리지 마세요.

운영 정책과 확인 방법은
[`../docs/current/product/WEB_SEARCH_POLICY.md`](../docs/current/product/WEB_SEARCH_POLICY.md)를
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

## PostgreSQL–Milvus 영화 동기화

영화 데이터의 기준 원본은 PostgreSQL이다. TMDB 데이터를 Milvus에 직접 추가하지
않고, PostgreSQL에서 성인물 제외와 메타데이터 검증을 마친 뒤 CSV로 내보내
`rag/rebuild_movies_from_csv.py`로 새 컬렉션을 만든다.

```bash
python -m rag.rebuild_movies_from_csv \
  --csv data/movies_postgres.csv \
  --collection movies_postgres_YYYYMMDD \
  --batch-size 16 --device cuda --max-length 512
```

기존 컬렉션을 즉시 삭제하지 않는다. 새 컬렉션의 행 수, `tmdb_id` 누락·초과·중복,
검색 결과를 검증한 다음 `movies_active` 별칭을 새 컬렉션에 연결한다. 검색 코드는
기본적으로 이 별칭을 사용하며 `MOVIE_COLLECTION_NAME` 환경변수로 변경할 수 있다.
문제가 생기면 별칭을 이전 `movies` 컬렉션으로 되돌려 롤백한다.

일일 변경분은 전체 컬렉션을 재생성하지 않고 인증된
`POST /internal/movies/sync` API로 전달한다. 이 API는 변경 영화의 임베딩을 먼저
생성한 뒤 `tmdb_id`가 같은 기존 행을 교체한다. Backend와 동일한
`AI_SYNC_TOKEN`을 서비스 환경변수로 설정해야 한다.

2026-08-07 최초 전체 재색인 결과는 PostgreSQL과 Milvus가 각각 32,302편이며,
`tmdb_id` 누락·초과·중복은 모두 0건이다. 실제 컬렉션은
`movies_postgres_20260807`, 활성 별칭은 `movies_active`다.

같은 날 일일 증분 동기화를 처음 실행해 신규 5편과 기존 변경 634편을 반영했다.
반영 후 PostgreSQL과 `movies_active`는 각각 32,307편이며 `tmdb_id` 중복은 0건이다.
