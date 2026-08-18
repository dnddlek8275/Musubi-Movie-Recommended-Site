# API 오류 응답 정책

현재 Frontend는 평평한 응답과 FastAPI `HTTPException`의 `detail` 응답을 모두
읽을 수 있다.

## 상태 코드

- 정상 처리: 해당 API의 2xx
- 기존 기능상 `failure`: 현재 호환성을 위해 기존 상태 코드 유지
- 인증·권한·검증 실패: 해당 API가 명시한 4xx
- 예상하지 못한 Backend 예외: 500
- 외부 AI 연결·응답 실패: 502
- 외부 AI timeout: 504
- SMTP 발송 실패: 503

`failure`는 검색 결과 없음, 사용자가 삭제할 데이터 없음처럼 애플리케이션이
예상한 결과다. 이번 정리에서는 Frontend 동작을 바꿀 수 있으므로 모든
`failure`를 일괄적으로 4xx로 전환하지 않았다.

## 응답 본문

Backend가 직접 만드는 일반 서버 오류는 기존 Frontend 계약을 유지한다.

```json
{
  "state": "error",
  "message": "사용자에게 표시할 안전한 메시지"
}
```

FastAPI `HTTPException`은 다음 형태다.

```json
{
  "detail": {
    "state": "error",
    "message": "사용자에게 표시할 안전한 메시지"
  }
}
```

Frontend의 `getResponseState()`와 `getErrorMessage()`는 두 형태를 모두 처리한다.

## 보안 원칙

- 응답에 `str(exception)`을 포함하지 않는다.
- DB 주소, SQL 오류, 내부 파일 경로와 외부 서비스 응답 본문을 노출하지 않는다.
- 상세 예외는 애플리케이션 로그에서 관리하고 사용자에게는 안전한 메시지만
  반환한다.
- 서비스 함수가 발생시킨 `HTTPException`은 라우터에서 HTTP 200이나 500으로
  바꾸지 않고 원래 상태 코드를 유지한다.
