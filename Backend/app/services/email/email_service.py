from email.message import EmailMessage
from html import escape

import aiosmtplib
import certifi

from app.core.config import settings


CONTACT_CATEGORY_LABELS = {
    "service": "서비스 이용 문의",
    "movie_data": "영화 정보 수정 요청",
    "ai": "AI 추천·대화 오류 신고",
    "account": "계정 및 로그인 문의",
    "other": "기타 문의",
}


def build_contact_inquiry_message(
    *, inquiry_id: int, category: str, reply_email: str, subject: str, content: str, member: bool
) -> EmailMessage:
    category_label = CONTACT_CATEGORY_LABELS.get(category, "기타 문의")
    message = EmailMessage()
    message["From"] = f"Musubi <{settings.MAIL_FROM}>"
    message["To"] = settings.CONTACT_RECEIVER_EMAIL
    message["Reply-To"] = reply_email
    message["Subject"] = f"[Musubi 문의 #{inquiry_id}] {subject}"
    message.set_content(
        f"""문의 번호: {inquiry_id}
문의 유형: {category_label}
회원 여부: {"회원" if member else "비회원"}
회신 이메일: {reply_email}
제목: {subject}

{content}"""
    )
    safe_content = escape(content).replace("\n", "<br>")
    message.add_alternative(
        f"""<!doctype html><html lang="ko"><body style="margin:0;padding:28px;background:#0b1115;color:#f4f6f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans KR',sans-serif;">
<div style="max-width:640px;margin:0 auto;padding:30px;border:1px solid #29343a;border-radius:20px;background:#151d21;">
<div style="color:#f7a916;font-size:12px;font-weight:800;letter-spacing:2px;">MUSUBI CONTACT</div>
<h1 style="margin:12px 0 24px;font-size:24px;">새 문의가 접수되었습니다</h1>
<table style="width:100%;border-collapse:collapse;color:#dce2e5;font-size:14px;line-height:1.7;">
<tr><td style="width:110px;padding:7px 0;color:#8f9ba1;">문의 번호</td><td>#{inquiry_id}</td></tr>
<tr><td style="padding:7px 0;color:#8f9ba1;">문의 유형</td><td>{escape(category_label)}</td></tr>
<tr><td style="padding:7px 0;color:#8f9ba1;">회원 여부</td><td>{"회원" if member else "비회원"}</td></tr>
<tr><td style="padding:7px 0;color:#8f9ba1;">회신 이메일</td><td>{escape(reply_email)}</td></tr>
<tr><td style="padding:7px 0;color:#8f9ba1;">제목</td><td>{escape(subject)}</td></tr>
</table>
<div style="margin-top:22px;padding:20px;border-radius:14px;background:#0e1519;color:#eef1f2;font-size:15px;line-height:1.75;">{safe_content}</div>
</div></body></html>""",
        subtype="html",
    )
    return message


async def send_contact_inquiry_email(**kwargs):
    message = build_contact_inquiry_message(**kwargs)
    await aiosmtplib.send(
        message,
        hostname=settings.MAIL_HOST,
        port=settings.MAIL_PORT,
        username=settings.MAIL_USERNAME,
        password=settings.MAIL_PASSWORD,
        start_tls=True,
        cert_bundle=certifi.where(),
        timeout=30,
    )


def build_contact_reply_message(*, email: str, inquiry_id: int, subject: str, body: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = f"Musubi <{settings.MAIL_FROM}>"
    message["To"] = email
    message["Subject"] = f"[Musubi 문의 #{inquiry_id}] {subject}"
    message.set_content(f"안녕하세요. Musubi입니다.\n\n{body}\n\n감사합니다.\nMusubi 드림")
    safe_body = escape(body).replace("\n", "<br>")
    message.add_alternative(
        f"""<!doctype html><html lang="ko"><body style="margin:0;padding:28px;background:#0b1115;color:#f4f6f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans KR',sans-serif;">
<div style="max-width:640px;margin:0 auto;padding:30px;border:1px solid #29343a;border-radius:20px;background:#151d21;">
<div style="color:#f7a916;font-size:12px;font-weight:800;letter-spacing:2px;">MUSUBI SUPPORT</div>
<h1 style="margin:12px 0 8px;font-size:24px;">문의에 답변드려요</h1>
<p style="margin:0 0 22px;color:#8f9ba1;font-size:13px;">문의 번호 #{inquiry_id}</p>
<div style="padding:20px;border-radius:14px;background:#0e1519;color:#eef1f2;font-size:15px;line-height:1.8;">{safe_body}</div>
<p style="margin:22px 0 0;color:#8f9ba1;font-size:12px;line-height:1.7;">추가로 도움이 필요하시면 이 메일에 회신해 주세요.<br>감사합니다. Musubi 드림</p>
</div></body></html>""",
        subtype="html",
    )
    return message


async def send_contact_reply_email(**kwargs):
    message = build_contact_reply_message(**kwargs)
    await aiosmtplib.send(
        message,
        hostname=settings.MAIL_HOST,
        port=settings.MAIL_PORT,
        username=settings.MAIL_USERNAME,
        password=settings.MAIL_PASSWORD,
        start_tls=True,
        cert_bundle=certifi.where(),
        timeout=30,
    )


def build_signup_verification_message(email: str, code: str, account_change: bool = False) -> EmailMessage:
    """메일 클라이언트 호환성을 고려한 회원가입 인증 메일을 생성한다."""
    expire_minutes = settings.EMAIL_VERIFICATION_EXPIRE_MINUTES
    message = EmailMessage()
    message["From"] = f"Musubi <{settings.MAIL_FROM}>"
    message["To"] = email
    message["Subject"] = f"[Musubi] 이메일 인증번호 {code}"
    intro_text = "Musubi 계정 이메일 변경을 요청하셨습니다." if account_change else "Musubi에 오신 것을 환영합니다."
    description = "Musubi 계정 이메일 변경을 위한 인증번호입니다." if account_change else "Musubi 가입을 위한 인증번호입니다."
    message.set_content(
        f"""
{intro_text}

이메일 인증번호: {code}
유효시간: {expire_minutes}분

인증번호는 다른 사람에게 알려주지 마세요.
본인이 요청하지 않았다면 이 메일을 무시해 주세요.
        """.strip()
    )
    message.add_alternative(
        f"""<!doctype html>
<html lang="ko">
  <body style="margin:0;padding:0;background:#0b0912;color:#f7f4ff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans KR',Arial,sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#0b0912;">
      <tr>
        <td align="center" style="padding:40px 16px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;background:#171321;border:1px solid #30273f;border-radius:24px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.35);">
            <tr>
              <td style="height:6px;background:linear-gradient(90deg,#8b5cf6,#ec4899,#f59e0b);font-size:0;line-height:0;">&nbsp;</td>
            </tr>
            <tr>
              <td style="padding:34px 38px 12px;text-align:center;">
                <div style="display:inline-block;padding:8px 14px;border:1px solid #4c3d66;border-radius:999px;color:#c4b5fd;font-size:12px;font-weight:800;letter-spacing:2px;">MUSUBI</div>
                <h1 style="margin:22px 0 10px;color:#ffffff;font-size:27px;line-height:1.35;">이메일 인증을 완료해 주세요</h1>
                <p style="margin:0;color:#aaa2b8;font-size:15px;line-height:1.7;">영화와 취향이 이어지는 공간,<br>{description}</p>
              </td>
            </tr>
            <tr>
              <td style="padding:24px 38px 10px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#0f0c17;border:1px solid #403451;border-radius:18px;">
                  <tr>
                    <td align="center" style="padding:27px 20px 10px;color:#8f879c;font-size:12px;font-weight:700;letter-spacing:1.4px;">VERIFICATION CODE</td>
                  </tr>
                  <tr>
                    <td align="center" style="padding:0 20px 26px;color:#ffffff;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:40px;font-weight:800;letter-spacing:10px;line-height:1.2;">{code}</td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:14px 38px 34px;text-align:center;">
                <p style="margin:0 0 18px;color:#ddd6e8;font-size:14px;line-height:1.7;">인증번호는 <strong style="color:#c4b5fd;">{expire_minutes}분 동안</strong> 유효합니다.</p>
                <div style="padding:14px 16px;background:#21192a;border-radius:12px;color:#9f96aa;font-size:12px;line-height:1.65;text-align:left;">🔒 Musubi는 이메일로 비밀번호를 요청하지 않습니다. 인증번호를 다른 사람에게 알려주지 마세요.</div>
              </td>
            </tr>
            <tr>
              <td style="padding:20px 30px;background:#100d17;border-top:1px solid #2b2436;text-align:center;color:#756d80;font-size:11px;line-height:1.65;">본인이 요청하지 않았다면 이 메일을 무시해 주세요.<br>© Musubi</td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>""",
        subtype="html",
    )
    return message


async def send_signup_verification_code(
        email : str,
        code : str,
):
    message = build_signup_verification_message(email, code)
    # 설정된 SMTP 서버로 전송
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


async def send_account_email_verification_code(email: str, code: str):
    message = build_signup_verification_message(email, code, account_change=True)
    await aiosmtplib.send(
        message,
        hostname=settings.MAIL_HOST,
        port=settings.MAIL_PORT,
        username=settings.MAIL_USERNAME,
        password=settings.MAIL_PASSWORD,
        start_tls=True,
        cert_bundle=certifi.where(),
        timeout=30,
    )


def build_password_reset_message(email: str, reset_url: str) -> EmailMessage:
    """회원가입 인증 메일과 같은 Musubi 양식의 비밀번호 재설정 메일을 생성한다."""
    expire_minutes = settings.PASSWORD_RESET_EXPIRE_MINUTES
    safe_reset_url = escape(reset_url, quote=True)
    message = EmailMessage()
    message["From"] = f"Musubi <{settings.MAIL_FROM}>"
    message["To"] = email
    message["Subject"] = "[Musubi] 비밀번호 재설정 안내"
    message.set_content(
        f"""
Musubi 비밀번호 재설정을 요청하셨습니다.
아래 링크에서 새로운 비밀번호를 설정해 주세요.

{reset_url}
유효시간: {expire_minutes}분

본인이 요청하지 않았다면 이 메일을 무시해 주세요.
        """.strip()
    )
    message.add_alternative(
        f"""<!doctype html>
<html lang="ko">
  <body style="margin:0;padding:0;background:#0b0912;color:#f7f4ff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans KR',Arial,sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#0b0912;">
      <tr>
        <td align="center" style="padding:40px 16px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;background:#171321;border:1px solid #30273f;border-radius:24px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.35);">
            <tr>
              <td style="height:6px;background:linear-gradient(90deg,#8b5cf6,#ec4899,#f59e0b);font-size:0;line-height:0;">&nbsp;</td>
            </tr>
            <tr>
              <td style="padding:34px 38px 12px;text-align:center;">
                <div style="display:inline-block;padding:8px 14px;border:1px solid #4c3d66;border-radius:999px;color:#c4b5fd;font-size:12px;font-weight:800;letter-spacing:2px;">MUSUBI</div>
                <h1 style="margin:22px 0 10px;color:#ffffff;font-size:27px;line-height:1.35;">비밀번호를 다시 설정해 주세요</h1>
                <p style="margin:0;color:#aaa2b8;font-size:15px;line-height:1.7;">영화와 취향이 이어지는 공간,<br>Musubi 계정의 비밀번호 재설정을 요청하셨습니다.</p>
              </td>
            </tr>
            <tr>
              <td style="padding:24px 38px 10px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#0f0c17;border:1px solid #403451;border-radius:18px;">
                  <tr>
                    <td align="center" style="padding:25px 20px 12px;color:#8f879c;font-size:12px;font-weight:700;letter-spacing:1.4px;">PASSWORD RESET</td>
                  </tr>
                  <tr>
                    <td align="center" style="padding:0 20px 28px;">
                      <a href="{safe_reset_url}" style="display:inline-block;padding:14px 26px;border-radius:12px;background:#8b5cf6;color:#ffffff;font-size:15px;font-weight:800;line-height:1.2;text-decoration:none;">새 비밀번호 설정하기</a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:14px 38px 34px;text-align:center;">
                <p style="margin:0 0 18px;color:#ddd6e8;font-size:14px;line-height:1.7;">재설정 링크는 <strong style="color:#c4b5fd;">{expire_minutes}분 동안</strong> 유효합니다.</p>
                <div style="padding:14px 16px;background:#21192a;border-radius:12px;color:#9f96aa;font-size:12px;line-height:1.65;text-align:left;">🔒 Musubi는 이메일로 비밀번호를 요청하지 않습니다. 새 비밀번호는 Musubi 화면에서만 입력해 주세요.</div>
              </td>
            </tr>
            <tr>
              <td style="padding:20px 30px;background:#100d17;border-top:1px solid #2b2436;text-align:center;color:#756d80;font-size:11px;line-height:1.65;">본인이 요청하지 않았다면 이 메일을 무시해 주세요.<br>© Musubi</td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>""",
        subtype="html",
    )
    return message


# 비밀번호 재설정 링크 이메일로 보내는 함수
async def send_password_reset_email(
        email: str,
        reset_url: str,
):
    message = build_password_reset_message(email, reset_url)

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
