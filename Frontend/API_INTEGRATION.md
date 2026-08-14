# Musubi 프론트엔드 API·STT 연동 기준

작성 기준: 2026-07-29

## 공통 설정

- 실제 API 주소는 `VITE_API_BASE_URL`로 설정한다.
- 로컬 예시는 `http://127.0.0.1:8080`이다.
- Access API에는 `Authorization: Bearer <access_token>`을 전송한다.
- refresh cookie를 위해 `credentials: "include"`를 사용한다.
- HTTP 성공 여부뿐 아니라 JSON의 `state` 또는 예외적인 `status`도 확인한다.
- `ACCESS_TOKEN_EXPIRED`인 HTTP 401만 refresh 후 한 번 재시도한다.

전체 API 목록에는 다음 사용자 선호 일괄 삭제 경로가 포함되어야 한다.

```http
DELETE /user/preferences/{preference_type}
```

이를 포함하면 문서 머리말의 46 URL path / 48 HTTP operation과 일치한다.

## STT 계약

```http
POST /audio/transcribe
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

- FormData 필드명: `audio`
- STT 요청에는 `audio`만 보내며 `room_id`, `character`, 캐릭터 목록을 추가하지 않는다.
- 최대 크기: 20MB
- 지원 형식: WebM, WAV, MP3, M4A, OGG
- multipart `Content-Type`은 브라우저가 boundary와 함께 생성하므로 직접 설정하지 않는다.
- 성공 텍스트: `data.text`
- `state !== "success"`이면 HTTP 200이어도 실패로 처리한다.
- `state`가 `failure` 또는 `error`이면 `data.text`가 없는 것으로 간주하고 채팅 API를 호출하지 않는다.
- 서버의 `error` 원문은 사용자에게 표시하지 않고 안전한 `message`만 사용한다.
- 캐릭터 이름·별칭·띄어쓰기·조사 보정은 백엔드 결과를 그대로 사용한다.
- `data.text`의 쉼표·마침표·물음표를 프론트에서 일괄 삭제하거나 치환하지 않는다.

성공 예시:

```json
{
  "state": "success",
  "message": "음성을 텍스트로 변환했습니다.",
  "data": { "text": "오늘 볼 만한 영화 추천해 줘" }
}
```

## 자동 채팅방 연결

`POST /chat/auto`는 새 기본 채팅의 첫 메시지에만 호출한다. 성공 응답의
`data.room_id`를 현재 프론트 대화에 저장하고, 두 번째 메시지부터는 반드시
`POST /chat/rooms/{room_id}/messages`를 호출한다.

```json
{
  "message": "오늘 볼 영화 추천해줘",
  "character": null
}
```

## 기존 채팅방 연결

- general 방과 캐릭터 1:1 방은 `POST /chat/rooms/{room_id}/messages`로 이어서 대화한다.
- `room_id`는 요청 본문이 아니라 URL 경로에 넣는다.
- 요청 본문은 `{ "content": "계속 이야기해줘", "character": null }` 형식이다.
- general 방에서 캐릭터가 응답해도 동일한 `room_id`와 `room_type: "general"`을 유지한다.
- 그룹 방은 현재 이어 말하기를 지원하지 않는다.
- `GET /chat/rooms/{room_id}/messages`와 `DELETE /chat/rooms/{room_id}`에는 저장한 방 ID를 사용한다.

## 적용된 UI 흐름

1. 마이크 버튼을 누르면 권한을 요청하고 녹음을 시작한다.
2. 녹음 중에는 버튼이 빨간 중지 버튼으로 바뀌고 경과 시간이 툴팁에 표시된다.
3. 다시 누르면 녹음을 종료하고 STT 요청을 보낸다.
4. 변환 중에는 버튼을 비활성화해 중복 요청을 막는다.
5. `state === "success"`이고 `data.text`가 있을 때만 다음 단계로 진행한다.
6. 성공한 텍스트는 상태에서 다시 읽지 않고 `sendMessage(text)`에 직접 전달해 즉시 전송한다.
7. `failure/error`이면 서버의 안전한 `message`를 표시하고 모든 채팅 API 호출을 중단한다.
8. 컴포넌트가 종료되면 녹음 track과 진행 중인 요청을 정리한다.

적용 화면:

- 일반 1:1 캐릭터 채팅
- CineBuddy 자동 채팅
- 그룹 채팅

관련 구현:

- `src/api.js`의 `transcribeAudio()`
- `src/components/chat/SttMicButton.jsx`
- 각 채팅 화면의 `SttMicButton` 사용부

명세는 입력창에서 사용자가 확인한 뒤 전송하는 흐름을 권장하지만, 현재 제품 요구사항은
STT 완료 후 엔터 없이 즉시 전송하는 방식이다. React 상태 갱신 시점 때문에 이전 입력값이
전송되지 않도록 세 화면 모두 STT 반환 문자열을 채팅 함수 인자로 직접 넘긴다.

## 주의

첨부된 전체 API 명세 사본은 `9.9 Admin 공통 인증·검... (12KB 남음)`에서
잘려 있으므로, Audio·System·최종 체크리스트까지 포함된 원본을 확보하면 이 문서와
병합해 최종본으로 갱신해야 한다.
