# Musubi 최종 발표용 문서 세트

- 기준일: 2026-08-14
- 버전: Final 1.0
- 기준: 운영 코드, Kubernetes/클라우드 구성, 현행 제품·AI·데이터 정책

## 문서

- [Musubi_WBS_최종.docx](./Musubi_WBS_최종.docx)
- [Musubi_IA_최종.docx](./Musubi_IA_최종.docx)
- [Musubi_클라우드아키텍처_최종.docx](./Musubi_클라우드아키텍처_최종.docx)
- [Musubi_요구사항정의서_최종.docx](./Musubi_요구사항정의서_최종.docx)
- [Musubi_기획서_최종.docx](./Musubi_기획서_최종.docx)
- [Musubi_기능정의서_최종.docx](./Musubi_기능정의서_최종.docx)
- [Musubi_화면설계서_최종.docx](./Musubi_화면설계서_최종.docx)

## 상태 표기

- 완료: 운영 또는 코드에서 확인된 기능
- 부분: 환경 조건, 성능/운영 제약 또는 일부 관측만 적용
- 계획: 아직 운영에 적용하지 않은 향후 작업

## 최신화 원칙

- MySQL, Redis, A100, API Gateway, 외부 GPT 의존 등 폐기된 초기 가정은 제거했습니다.
- 현재 구조는 PostgreSQL/PgBouncer, KKE 2노드, Tesla T4 GPU VM, 자체 LLM, Milvus, Object Storage, Container Registry를 기준으로 합니다.
- Private Application Server와 Kubernetes Persistent Volume은 사용하지 않는 범위로 명시했습니다.
- 로컬의 미검증 AI 모델 실험은 운영 완료 기능에 포함하지 않았습니다.
