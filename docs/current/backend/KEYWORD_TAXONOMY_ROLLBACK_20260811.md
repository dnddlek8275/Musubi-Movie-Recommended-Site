# 활동 취향 키워드 체계 변경 및 롤백 기록 (2026-08-11)

## 변경 전

- `Backend/app/services/preference_service.py`의 허용 목록은 영어·한국어 별칭을 포함해 123개였다.
- 영어·한국어 및 유사 표현이 서로 다른 `preference_value`로 저장될 수 있었다.
- 변경 전 목록은 `LEGACY_LEARNABLE_KEYWORDS`로 코드에 그대로 보존되어 있다.

## 현재 적용

- `CURATED_LEARNABLE_KEYWORDS`: 대표 키 60개
- `KEYWORD_CANONICAL_MAP`: 한국어·영어 별칭과 유사 표현을 대표 키로 통합
- `maze`, `teleportation`은 활동 기반 키워드 학습에서 제외
- 영화 및 사용자 행동 원본 데이터는 변경하지 않고 `user_preference_scores`만 재계산

## DB 롤백 자료

- 백업 테이블: `user_preference_scores_backup_20260811`
- 백업 행 수: 188
- 60개 체계 재계산 직후 행 수: 178

## 롤백 방법

### 최신 행동 기록까지 이전 체계로 다시 계산

1. `USE_CURATED_KEYWORD_TAXONOMY = False`로 변경한다.
2. 백엔드를 재빌드한다.
3. `python scripts/rebuild_preference_scores.py`를 실행한다.

이 방법은 백업 이후 새로 발생한 행동도 포함한다.

### 2026-08-11 변경 직전 점수로 즉시 복원

```sql
BEGIN;
TRUNCATE TABLE user_preference_scores;
INSERT INTO user_preference_scores
SELECT * FROM user_preference_scores_backup_20260811;
COMMIT;
```

이 방법은 정확히 변경 직전 188개 점수 행으로 돌아간다.
