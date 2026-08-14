# Musubi chatai 음성

OpenVoice V2와 MeloTTS를 사용하는 무료 로컬 TTS입니다. 현재 캐릭터 음성은
`chatai` 하나이며, 실제 아동을 복제하지 않은 합성 음성입니다.

## 음성 특성

| 구분 | 현재 설정 | 적용 목적 |
| --- | --- | --- |
| TTS 엔진 | OpenVoice V2 + MeloTTS | 무료 로컬 음성 합성 |
| 음성 이름 | `chatai` | AI 채팅 전용 프리셋 |
| 음성 성격 | 밝고 가벼운 초등학교 5학년 정도의 합성 음색 | 친근한 AI 챗봇 표현 |
| 실제 음성 복제 | 사용하지 않음 | 특정 인물·실제 아동 음성 복제 방지 |
| 지원 언어 | `AUTO`, `KR`, `EN` | 한국어·영어 자동 감지 또는 직접 지정 |
| 피치 | 기본 음성 대비 `+4` 반음 | 어린 느낌의 높은 음역 형성 |
| 내부 합성 속도 | 요청 `rate × 1.06` | 답답하지 않은 발화 속도 |
| 사용자 속도 | `0.8x`, `1.0x`, `1.2x` | 채팅 화면에서 순환 선택 |
| 저역 정리 | High-pass `95Hz`, `220Hz -2dB` | 탁하고 무거운 저음 감소 |
| 명료도 | `2800Hz +2.5dB`, Q `1.1` | 자음과 말소리 선명도 향상 |
| 고역 제한 | Low-pass `10500Hz` | 과도한 고역과 거친 잡음 억제 |
| 컴프레서 | threshold `-20dB`, ratio `2.2`, attack `8ms`, release `120ms`, makeup `1.5dB` | 음량 편차 완화 |
| 리미터 | limit `0.94` | 피크 왜곡 방지 |
| 긴 답변 처리 | 문장 단위, 최대 약 `70자` | 첫 음성 생성 지연 단축 |
| 선행 합성 | 현재 문장 재생 중 다음 문장 합성 | 문장 사이 대기 시간 감소 |
| 재생 대상 | AI 답변만 | 사용자 메시지·오류 메시지 제외 |
| 설정 저장 | `cineverse.chat.tts.enabled` | 브라우저에서 ON/OFF 상태 유지 |

## 설치와 실행

```bash
cd /Users/apple/Documents/cineverse/tts-service
chmod +x setup.sh start.sh
./setup.sh
./start.sh
```

서버 주소는 `http://127.0.0.1:5001`입니다.

## 테스트 코드

```bash
cd /Users/apple/Documents/cineverse/tts-service

.openvoice-env/bin/python tune_voice.py \
  --voice chatai \
  --character chatai \
  --rate 1.0 \
  --language KR \
  --text "안녕! 오늘은 어떤 영화를 같이 찾아볼까?" \
  --output samples/chatai-test.wav \
  --play
```

영어 테스트:

```bash
.openvoice-env/bin/python tune_voice.py \
  --language EN \
  --text "Hi! What movie should we watch today?" \
  --output samples/chatai-english.wav \
  --play
```

`--rate` 권장 범위는 `0.95~1.08`입니다. 값이 높을수록 빠르게 말합니다.

## API 테스트

```bash
curl -X POST http://127.0.0.1:5001/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":"안녕! 반가워.","character":"chatai","voice":"chatai","rate":1.0,"language":"KR"}' \
  --output chatai.wav
```

음성 목록 확인:

```bash
curl http://127.0.0.1:5001/voices
```

## 채팅 페이지에서 사용

채팅 상단의 `TTS OFF` 버튼을 눌러 `TTS ON`으로 바꾸면 AI 답변만 `chatai` 음성으로
자동 재생됩니다. 자동 채팅에서는 긴 답변을 최대 약 70자의 문장 단위로 합성하고,
각 음성이 시작될 때 해당 글자도 함께 표시합니다. 사용자가 보낸 메시지와 오류 메시지는
재생하지 않습니다. 설정은 브라우저에 저장되며, OFF로 전환하면 현재 재생도 즉시
중지됩니다.

## 직접 조정

[app.py](./app.py)의 `apply_chatai_style()`에서 다음 값을 변경한 후 서버를
재시작합니다.

- `4 / 12`: 피치. `3`은 더 차분하고 `5`는 더 높습니다.
- `1.06`: 기본 발화 속도. `1.03~1.08` 권장
- `equalizer=f=2800...g=2.5`: 발음의 밝기와 명료도

OpenVoice V2는 MIT 라이선스입니다. 실제 사람의 참조 음성을 사용할 때에는 반드시
본인 음성 또는 명시적으로 사용 허가를 받은 음성만 사용하세요.
