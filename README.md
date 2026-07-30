# CineVerse

CineVerse는 영화 탐색, 개인화 추천, AI 캐릭터 대화를 제공하는 웹
서비스입니다. 이 저장소는 애플리케이션과 인프라 코드를 함께 관리하는
monorepo입니다.

## 저장소 구성

```text
.
├── AI/          # RAG, 캐릭터·영화 추천, GPU AI API
├── Backend/     # FastAPI API, 인증, PostgreSQL 연동
├── Frontend/    # React 웹 애플리케이션
├── Add-on/      # 선택형 TTS·GPU 모니터링·프로토타입
├── Infra/       # 클라우드 및 Kubernetes 배포 코드
└── docs/        # 요구사항, DB, 아키텍처 및 운영 문서
```

## 관리 기준

- 루트 Git 저장소 하나에서 `AI`, `Backend`, `Frontend`, `Infra`를 함께
  버전 관리합니다.
- 환경변수, SSH 개인키, 모델 가중치, 벡터 생성물과 운영 데이터는 Git에
  커밋하지 않습니다.
- AI 운영 모델과 Milvus 데이터는 GPU 서버 이미지 및 별도 백업으로
  관리합니다.
- 배포 구성은 현재 애플리케이션 코드와 운영 중인 AI 서버를 기준으로
  작성하며, 과거 기획 문서는 참고 자료로만 사용합니다.

## 구성 요소별 안내

- [Backend 안내](Backend/README.md)
- [Frontend 안내](Frontend/README.md)
- [AI 안내](AI/README.md)
- [Infra 안내](Infra/README.md)
- [선택 기능 안내](Add-on/README.md)
- [문서 안내](docs/README.md)
- [DB 테이블](docs/current/backend/DB_TABLES.md)
