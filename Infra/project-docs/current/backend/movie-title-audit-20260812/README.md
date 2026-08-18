# 영화 한국어 제목 감사 (2026-08-12)

운영 PostgreSQL의 영화 32,310편 중 TMDB ID가 있는 32,309편을 TMDB `language=ko-KR` 상세 응답과 대조했다.

## 결과

- 공식 한국어 제목으로 변경 가능한 영화: 871편
- TMDB `ko-KR`에도 한글 제목이 없는 영화: 16,440편
- TMDB 상세정보가 404인 영화: 29편
- TMDB ID가 없는 영화: 1편
- 감사 실패: 0편

## 파일

- `official-korean-title-changes.csv`: 현재 제목과 공식 `ko-KR` 제목이 다르고, 공식 제목에 한글이 포함된 영화
- `no-official-korean-title.csv`: TMDB `ko-KR` 제목에도 한글이 없어 원제를 유지할 영화
- `tmdb-unavailable.csv`: PostgreSQL에는 있지만 TMDB 상세정보가 404인 영화

## 적용 원칙

1. TMDB `ko-KR` 상세 응답의 `title`에 한글이 있을 때만 제목을 변경한다.
2. 한글 제목이 없으면 기계 번역이나 임의 번역을 하지 않고 현재 제목을 유지한다.
3. TMDB ID를 기준으로 적용해 동명 영화를 잘못 변경하지 않는다.
4. 제목이 변경된 영화는 `movie_vector_sync_jobs`에 `upsert`로 등록해 PostgreSQL과 Milvus를 다시 동기화한다.
5. 이 감사 작업 자체는 조회 전용으로 실행했으며 운영 DB에는 변경을 적용하지 않았다.
