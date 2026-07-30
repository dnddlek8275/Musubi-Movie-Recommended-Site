# CineVerse Backend

CineVerse의 영화 탐색, 개인화 추천, 캐릭터 채팅, 회원 및 관리자 기능을
제공하는 FastAPI 백엔드입니다.

## 서버 구성

- Python 3.12 이상
- FastAPI, Uvicorn
- PostgreSQL, SQLAlchemy 2, Alembic
- JWT 인증
- AI 서버, TMDB API, SMTP 연동

## 배포 준비

Python 3.12 이상과 PostgreSQL을 준비합니다.

```bash
cd Backend
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

## 환경변수

예시 파일을 복사하고 배포 환경에 맞게 값을 설정합니다.

```bash
cp .env.example .env
```

주요 환경변수:

| 변수 | 설명 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL 연결 주소 |
| `SECRET_KEY` | Access/Refresh Token 서명용 비밀키 |
| `AI_BASE_URL` | AI 서버 주소 |
| `CORS_ORIGINS` | 허용할 브라우저 출처를 쉼표로 구분한 목록 |
| `TMDB_ACCESS_TOKEN` | TMDB Read Access Token |
| `TMDB_API_KEY` | Access Token을 사용하지 않을 때의 TMDB API Key |
| `MAIL_HOST`, `MAIL_PORT` | SMTP 서버 주소와 포트 |
| `MAIL_USERNAME`, `MAIL_PASSWORD` | SMTP 인증 정보 |
| `MAIL_FROM` | 발신 이메일 주소 |
| `FRONTEND_BASE_URL` | 비밀번호 재설정 화면 주소 |

`.env`에는 DB 비밀번호, JWT 비밀키, API 토큰 등 민감정보가 포함되므로
Git에 커밋하지 않습니다. 운영 환경에서는 저장소 파일 대신 배포 플랫폼의
Secret 또는 환경변수 관리 기능을 사용하는 것을 권장합니다.

## 데이터베이스 적용

대상 데이터베이스를 생성한 뒤 마이그레이션을 적용합니다.

```bash
.venv/bin/alembic upgrade head
```

적용 상태는 다음 명령으로 확인합니다.

```bash
.venv/bin/alembic current
```

## 서버 실행

개발 환경:

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

운영 환경:

```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Docker 이미지:

```bash
docker build -t cineverse-backend .
docker run --rm --env-file .env -p 8080:8080 cineverse-backend
```

DB 마이그레이션은 애플리케이션 컨테이너를 여러 개 실행하기 전에 별도 작업으로
한 번만 수행합니다.

```bash
docker run --rm --env-file .env cineverse-backend alembic upgrade head
```

서버 실행 후 다음 주소를 확인할 수 있습니다.

| 용도 | 주소 |
| --- | --- |
| 상태 확인 | `GET /health` |
| DB 연결 확인 | `GET /db-test` |
| AI 서버 연결 확인 | `GET /ai-health` |
| Swagger UI | `/docs` |
| ReDoc | `/redoc` |

AI 서버를 사용하지 않는 환경에서는 `/ai-health`가 연결 실패를 반환할 수
있습니다.

## 배포 파일 구조

```text
.
├── app/                 # FastAPI 애플리케이션
│   ├── ai_client/       # AI 서버 연동
│   ├── api/             # API 라우터
│   ├── core/            # 설정, DB, 인증 공통 코드
│   ├── models/          # SQLAlchemy 모델
│   ├── repositories/    # 데이터 접근 계층
│   ├── schemas/         # 요청·응답 스키마
│   ├── services/        # 비즈니스 로직
│   └── uploads/         # 사용자 업로드 저장 경로
├── alembic/             # DB 마이그레이션
├── alembic.ini
├── Dockerfile
├── .dockerignore
├── .env.example
└── pyproject.toml
```

프로필 이미지는 기본적으로
`app/uploads/images/user_profiles`에 저장됩니다. 운영 서버에서는 이 경로를
영속 볼륨에 연결하고 별도로 백업해야 합니다.

## 운영 배포 확인사항

- 충분히 길고 예측하기 어려운 `SECRET_KEY`를 사용합니다.
- 실제 `.env`와 비밀정보를 Git에 올리지 않습니다.
- 배포 전에 DB를 백업하고 `alembic upgrade head`를 실행합니다.
- `CORS_ORIGINS`에는 운영 프론트엔드 주소만 지정합니다.
- HTTPS 환경에서는 Refresh Token Cookie의 `Secure` 설정을 적용합니다.
- 운영 서버에서는 Uvicorn의 `--reload` 옵션을 사용하지 않습니다.
- 사용자 업로드 경로를 영속 볼륨과 백업 대상에 포함합니다.
