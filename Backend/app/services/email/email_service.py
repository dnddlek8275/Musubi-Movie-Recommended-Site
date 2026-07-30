from email.message import EmailMessage

import aiosmtplib
import certifi

from app.core.config import settings


async def send_signup_verification_code(
        email : str,
        code : str,
):
    # 이메일 메시지 생성
    message = EmailMessage()
    # 발신자
    message["From"] = f"CineVerse <{settings.MAIL_FROM}>"
    # 수신자
    message["To"] = email
    # 제목
    message["Subject"] = "CineVerse 이메일 인증번호"
    # 본문
    message.set_content(
        f"""
안녕하세요. CineVerse입니다.
이메일 인증번호는 다음과 같습니다.
{code}
인증번호는 {settings.EMAIL_VERIFICATION_EXPIRE_MINUTES}분 동안 유효합니다.

본인이 요청하지 않았다면 이 메일을 무시해주세요.
감사합니다.
        """.strip()
    )
    # Gmail SMTP로 전송
    await aiosmtplib.send(
        message,
        hostname=settings.MAIL_HOST,
        port=settings.MAIL_PORT,
        username=settings.MAIL_USERNAME,
        password=settings.MAIL_PASSWORD,
        start_tls=True,

        # 신뢰할 TLS 인증서 목록을 명시
        # TLS 보안 연결 시 서버 인증서를 검증하기 위해 certifi가 제공하는 신뢰 가능한 인증서 파일을 사용하도록 지정하는 설정
        # TLS는 인터넷 통신 내용을 암호화하는 보안 기술
        cert_bundle= certifi.where(),
        timeout=30,
    )


# 비밀번호 재설정 링크 이메일로 보내는 함수
async def send_password_reset_email(
        email:str,
        reset_url : str,
):
   # 이메일 메시지 생성
    message = EmailMessage()
    # 발신자
    message["From"] = f"CineVerse <{settings.MAIL_FROM}>"
    # 수신자
    message["To"] = email
    # 제목
    message["Subject"] = "CineVerse 비밀번호 재설정"
    # 본문
    message.set_content(
        f"""
안녕하세요. CineVerse입니다.
아래 링크를 눌러 새로운 비밀번호를 설정해주세요.

{reset_url}
이 링크는 {settings.PASSWORD_RESET_EXPIRE_MINUTES}분 동안 유효합니다.

본인이 요청하지 않았다면 이 메일을 무시해주세요.
감사합니다.
        """.strip()
    )

    message.add_alternative(
        f"""
    <!DOCTYPE html>
    <html lang="ko">
    <body>
        <p>안녕하세요. CineVerse입니다.</p>
        <p>아래 버튼을 눌러 새로운 비밀번호를 설정해주세요.</p>

        <p>
        <a
            href="{reset_url}"
            style="
            display: inline-block;
            padding: 12px 20px;
            color: #ffffff;
            background-color: #7c3aed;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            "
        >
            새 비밀번호 설정하기
        </a>
        </p>

        <p>
        이 링크는 {settings.PASSWORD_RESET_EXPIRE_MINUTES}분 동안 유효합니다.
        </p>
        <p>본인이 요청하지 않았다면 이 메일을 무시해주세요.</p>
        <p>감사합니다.</p>
    </body>
    </html>
        """.strip(),
        subtype="html",
    
    )

    # Gmail SMTP로 전송
    await aiosmtplib.send(
        message,
        hostname=settings.MAIL_HOST,
        port=settings.MAIL_PORT,
        username=settings.MAIL_USERNAME,
        password=settings.MAIL_PASSWORD,
        start_tls=True,

        # 신뢰할 TLS 인증서 목록을 명시
        # TLS 보안 연결 시 서버 인증서를 검증하기 위해 certifi가 제공하는 신뢰 가능한 인증서 파일을 사용하도록 지정하는 설정
        # TLS는 인터넷 통신 내용을 암호화하는 보안 기술
        cert_bundle= certifi.where(),
        timeout=30,
    )