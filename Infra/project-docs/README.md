# Musubi 문서 안내

문서는 현재 배포 기준, 코드 참고자료, 과거 기록으로 구분합니다.

## 현재 기준

실제 인프라 구현과 운영 준비에 우선 사용하는 문서입니다.

### 인프라

- [멀티 AZ 운영 아키텍처](current/infra/multi-az-architecture.md)
- [클라우드 확장 계획 및 구현 기록](current/infra/cloud-architecture-expansion-20260818.md)
- [AI 용량·확장 정책](current/infra/ai-capacity-and-scaling.md)
- [인프라 기능요청서](current/infra/인프라 기능요청서.txt)
- [최종 인프라 논리 구조](current/infra/최종 인프라 논리 구조.png)
- [최종 인프라 물리 구조](current/infra/최종 인프라 물리 구조.png)
- [인프라 실무형 구성](current/infra/인프라실무형구성.svg)
- [GPU 서버 이전 가이드](current/infra/gpu서버 이전 가이드.md)

### 백엔드

- [DB 테이블](current/backend/DB_TABLES.md)
- [일일 박스오피스 자동 갱신](current/backend/BOX_OFFICE.md)
- [TMDB–PostgreSQL–Milvus 일일 동기화](current/backend/TMDB_DAILY_SYNC.md)

### 제품 정책

- [비회원 채팅 정책 및 후속 운영 계획](current/product/guest-chat-policy.md)
- [일반 채팅 입력 복구 응답](current/product/CHAT_INPUT_RECOVERY.md)
- [무무 일반 채팅 정체성·대화 품질 기준](current/product/MUMU_GENERAL_CHAT.md)
- [전체 대화 흐름 품질 감사](current/product/CONVERSATION_QUALITY_AUDIT_20260810.md)

## 참고자료

현재 코드의 배경과 제품 요구사항을 파악할 때 참고합니다. 작성 이후 코드와
정책이 변경된 부분이 있으므로 배포 설정의 최종 근거로 사용하지 않습니다.

### 제품·화면

- 기능정의서 v3 final
- 기획서 v4 final
- 요구사항정의서 v3 final
- IA
- WBS
- 팀플 화면설계서

## 발표용 최종 자료

- [2026-08-19 검증 기준 최신 자료](final-delivery/2026-08-17/README.md)
  - `Musubi_클라우드아키텍처_최신.docx`
  - `Musubi_AI_변경사항_최신.docx`
- [WBS·IA·요구사항·기획·기능·화면설계 최종본](final-delivery/2026-08-14/)

### 백엔드

- 백엔드 구조
- BE1/BE2 변경 정리

## 과거 문서

`archive/superseded/`에는 최종본으로 대체됐거나 현재 구조와 맞지 않는 과거
문서를 보관합니다. 내용 확인이 필요할 때만 사용합니다.

## 판단 우선순위

문서 간 내용이 충돌할 경우 다음 순서로 판단합니다.

1. 현재 실행 중인 코드와 운영 서버 상태
2. 2026-08-19 검증 기준 발표용 최신 자료
3. `current/` 문서
4. `reference/` 문서
5. `archive/` 문서
