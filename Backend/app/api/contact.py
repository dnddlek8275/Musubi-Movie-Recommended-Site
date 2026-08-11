import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.current_user import get_optional_current_user
from app.core.dependencies import get_db
from app.models.contact import ContactInquiry
from app.models.users import User
from app.schemas.contact import ContactInquiryRequest
from app.services.email.email_service import send_contact_inquiry_email


router = APIRouter(prefix="/contact", tags=["Contact"])
logger = logging.getLogger(__name__)

CONTACT_LIMIT_PER_HOUR = 3


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_contact_inquiry(
    request: ContactInquiryRequest,
    current_user: dict | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    user_id = int(current_user["user_id"]) if current_user else None
    email = str(request.email).strip().lower()

    if user_id is not None:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=401, detail={"message": "로그인 정보를 확인할 수 없습니다."})
        # 로그인 회원의 문의는 계정 소유가 확인된 이메일로만 접수한다.
        email = user.email.strip().lower()

    since = datetime.now(timezone.utc) - timedelta(hours=1)
    limiter = (
        or_(ContactInquiry.user_id == user_id, func.lower(ContactInquiry.email) == email)
        if user_id is not None
        else func.lower(ContactInquiry.email) == email
    )
    recent_count = db.query(func.count(ContactInquiry.id)).filter(limiter, ContactInquiry.created_at >= since).scalar() or 0
    if recent_count >= CONTACT_LIMIT_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"message": "문의가 연속으로 접수되었습니다. 한 시간 뒤 다시 시도해 주세요."},
        )

    inquiry = ContactInquiry(
        user_id=user_id,
        category=request.category,
        email=email,
        subject=request.subject,
        message=request.message,
    )
    db.add(inquiry)
    db.commit()
    db.refresh(inquiry)

    try:
        await send_contact_inquiry_email(
            inquiry_id=inquiry.id,
            category=inquiry.category,
            reply_email=inquiry.email,
            subject=inquiry.subject,
            content=inquiry.message,
            member=bool(user_id),
        )
        inquiry.delivery_status = "sent"
    except Exception:
        # 메일 장애가 나도 DB 접수 기록은 남아 있으므로 사용자 문의를 실패 처리하지 않는다.
        logger.exception("문의 알림 메일 전송 실패: inquiry_id=%s", inquiry.id)
        inquiry.delivery_status = "failed"
    db.commit()

    return {
        "state": "success",
        "message": "문의가 접수되었습니다. 확인 후 입력하신 이메일로 답변드릴게요.",
        "data": {"inquiry_id": inquiry.id},
    }
