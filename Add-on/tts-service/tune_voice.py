"""Generate and optionally play a chatai OpenVoice V2 test sample."""

import argparse
import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="chatai 음성 미리듣기")
    parser.add_argument("--voice", default="chatai")
    parser.add_argument("--character", default="chatai")
    parser.add_argument("--text", default="안녕! 오늘은 어떤 영화를 같이 찾아볼까?")
    parser.add_argument("--rate", type=float, default=1.0)
    parser.add_argument("--language", default="AUTO", choices=["AUTO", "KR", "EN"])
    parser.add_argument("--output", default="samples/chatai-test.wav")
    parser.add_argument("--url", default="http://127.0.0.1:5001")
    parser.add_argument("--play", action="store_true")
    args = parser.parse_args()

    payload = json.dumps({
        "voice": args.voice,
        "character": args.character,
        "text": args.text,
        "rate": args.rate,
        "language": args.language,
    }, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{args.url.rstrip('/')}/synthesize",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            output_path.write_bytes(response.read())
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise SystemExit(f"TTS 요청 실패 ({error.code}): {detail}") from error
    except urllib.error.URLError as error:
        raise SystemExit(f"TTS 서버 연결 실패: {error.reason}") from error

    print(f"voice={args.voice}")
    print(f"language={args.language}")
    print(f"rate={args.rate}")
    print(f"output={output_path}")
    if args.play:
        subprocess.run(["afplay", str(output_path)], check=True)


if __name__ == "__main__":
    main()
