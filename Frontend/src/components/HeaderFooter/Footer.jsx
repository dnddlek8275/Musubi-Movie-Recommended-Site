import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import Logo from './Logo.jsx';
import { submitContactInquiry } from '../../api.js';

const FOOTER_DETAILS = {
  sources: {
    title: '데이터 출처',
    intro: 'Musubi는 다음 데이터를 조합해 영화 탐색과 추천 화면을 구성합니다.',
    sections: [
      ['영화·배우 정보', '영화 제목, 줄거리, 장르, 평점, 배우 및 포스터 이미지 일부는 TMDB API와 이미지 서버를 통해 제공됩니다.'],
      ['Musubi 서비스 데이터', '서비스에 등록된 영화·배우·캐릭터 정보와 사용자가 선택한 취향 데이터를 추천과 화면 구성에 사용합니다.'],
      ['추천 결과', '선택한 장르·배우·키워드와 서비스 내 영화 반응을 바탕으로 추천 결과를 구성합니다.'],
    ],
  },
  terms: {
    title: '서비스 이용약관',
    intro: '이 안내는 현재 Musubi가 제공하는 기능을 기준으로 한 서비스 이용 기준입니다.',
    sections: [
      ['서비스 범위', 'Musubi는 영화 탐색, 취향 설정, 맞춤 추천, 캐릭터 대화 및 회원 계정 기능을 제공합니다.'],
      ['회원과 비회원 이용', '회원은 계정에 취향 정보를 저장할 수 있습니다. 비회원은 별도 계정 없이 서비스를 둘러볼 수 있으며 선택 정보는 해당 브라우저에 저장됩니다.'],
      ['외부 서비스 연동', '일부 영화 정보와 이미지는 외부 데이터 서비스 연동 상태에 따라 제공 범위가 달라질 수 있습니다.'],
      ['문의', '서비스 이용 중 발생한 문제와 계정 관련 요청은 공통 푸터의 문의하기 양식으로 접수할 수 있습니다.'],
    ],
  },
  privacy: {
    title: '개인정보 처리방침',
    intro: 'Musubi는 서비스 기능 제공에 필요한 범위에서 다음 정보를 처리합니다.',
    sections: [
      ['회원 정보', '회원가입 시 이메일과 닉네임을 저장합니다. 비밀번호는 원문이 아닌 해시값으로 저장하며, 사용자가 설정한 경우 프로필 이미지 정보를 함께 처리합니다.'],
      ['취향·이용 정보', '선호 장르·배우·키워드, 영화 반응 및 추천에 필요한 취향 점수를 저장해 개인화 기능에 사용합니다.'],
      ['로그인 정보', '로그인 상태 유지와 인증을 위해 세션 및 갱신 토큰 정보를 처리합니다.'],
      ['비회원 정보', '비회원의 취향, 대화 및 최근 추천 정보는 계정 데이터베이스가 아닌 이용 중인 브라우저의 로컬 저장소에 보관됩니다.'],
      ['문의 정보', '문의 접수 시 회신 이메일, 문의 유형, 제목과 내용을 처리하며 답변과 서비스 개선을 위해 사용합니다. 민감한 정보는 문의 내용에 입력하지 마세요.'],
    ],
  },
  company: {
    title: '회사 안내',
    intro: 'Musubi는 영화와 사람을 잇는 맞춤형 영화 추천 서비스입니다.',
    sections: [
      ['서비스', '취향 데이터와 대화를 바탕으로 사용자가 새로운 영화와 캐릭터를 발견할 수 있는 경험을 만듭니다.'],
      ['운영', 'Team Musubi가 서비스를 기획·개발·운영합니다.'],
      ['고객센터', '서비스, 계정 및 데이터 관련 문의는 공통 푸터의 문의하기 양식으로 접수해 주세요.'],
    ],
  },
};

const FOOTER_LINKS = [
  ['contact', '문의하기'],
  ['sources', '데이터 출처'],
  ['terms', '서비스 이용약관'],
  ['privacy', '개인정보 처리방침'],
  ['company', '회사 안내'],
];

const CONTACT_CATEGORIES = [
  ['service', '서비스 이용 문의'],
  ['movie_data', '영화 정보 수정 요청'],
  ['ai', 'AI 추천·대화 오류 신고'],
  ['account', '계정 및 로그인 문의'],
  ['other', '기타 문의'],
];

function FooterModal({ detail, onClose }) {
  const closeButtonRef = useRef(null);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };

    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', handleKeyDown);
    closeButtonRef.current?.focus();

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose]);

  return createPortal(
    <div
      className="site-info-modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section aria-labelledby="site-info-modal-title" aria-modal="true" className="site-info-modal" role="dialog">
        <header className="site-info-modal__header">
          <div>
            <span>MUSUBI GUIDE</span>
            <h2 id="site-info-modal-title">{detail.title}</h2>
          </div>
          <button ref={closeButtonRef} type="button" onClick={onClose} aria-label="닫기">×</button>
        </header>

        <div className="site-info-modal__body">
          <p className="site-info-modal__intro">{detail.intro}</p>
          {detail.sections.map(([heading, text]) => (
            <section key={heading}>
              <h3>{heading}</h3>
              <p>{text}</p>
            </section>
          ))}
        </div>
      </section>
    </div>,
    document.body,
  );
}

function ContactModal({ onClose, user }) {
  const closeButtonRef = useRef(null);
  const [category, setCategory] = useState('service');
  const [categoryOpen, setCategoryOpen] = useState(false);
  const [email, setEmail] = useState(user?.email || '');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const handleKeyDown = (event) => { if (event.key === 'Escape' && !busy) onClose(); };
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', handleKeyDown);
    closeButtonRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose]);

  const emailValid = /^\S+@\S+\.\S+$/.test(email.trim());
  const selectedCategoryLabel = CONTACT_CATEGORIES.find(([value]) => value === category)?.[1] || '문의 유형 선택';

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      const response = await submitContactInquiry({
        category,
        email: email.trim(),
        subject: subject.trim(),
        message: message.trim(),
        website: '',
      });
      setResult(response);
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setBusy(false);
    }
  };

  return createPortal(
    <div className="site-info-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) onClose(); }}>
      <section aria-labelledby="contact-modal-title" aria-modal="true" className="site-info-modal site-contact-modal" role="dialog">
        <header className="site-info-modal__header">
          <div><span>MUSUBI CONTACT</span><h2 id="contact-modal-title">문의하기</h2></div>
          <button ref={closeButtonRef} type="button" onClick={onClose} aria-label="닫기">×</button>
        </header>
        <div className="site-info-modal__body">
          {result ? (
            <div className="site-contact-success" role="status">
              <span aria-hidden="true">✓</span>
              <h3>문의가 접수되었습니다</h3>
              <p>{result.message}</p>
              {result.inquiryId ? <small>문의 번호 #{result.inquiryId}</small> : null}
              <button type="button" onClick={onClose}>닫기</button>
            </div>
          ) : (
            <form className="site-contact-form" noValidate onSubmit={handleSubmit}>
              <p>서비스 이용 중 불편한 점이나 영화 정보 수정 요청을 남겨주세요.</p>
              <label>문의 유형
                <span
                  className={`site-contact-select${categoryOpen ? ' is-open' : ''}`}
                  onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setCategoryOpen(false); }}
                  onKeyDown={(event) => {
                    if (event.key === 'Escape') {
                      event.stopPropagation();
                      setCategoryOpen(false);
                    }
                  }}
                >
                  <button type="button" aria-expanded={categoryOpen} aria-haspopup="listbox" onClick={() => setCategoryOpen((current) => !current)}>
                    <span>{selectedCategoryLabel}</span><span aria-hidden="true">⌄</span>
                  </button>
                  {categoryOpen ? <span className="site-contact-select__menu" role="listbox" aria-label="문의 유형">
                    {CONTACT_CATEGORIES.map(([value, label]) => <button className={category === value ? 'is-selected' : ''} key={value} type="button" role="option" aria-selected={category === value} onClick={() => { setCategory(value); setCategoryOpen(false); }}>{label}<span aria-hidden="true">{category === value ? '✓' : ''}</span></button>)}
                  </span> : null}
                </span>
              </label>
              <label>답변받을 이메일<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} readOnly={Boolean(user?.email)} placeholder="이메일 입력" /><small>{user?.email ? '로그인한 계정의 이메일로 답변드립니다.' : '답변을 받을 수 있는 이메일을 입력해 주세요.'}</small></label>
              <label>제목<input value={subject} onChange={(event) => setSubject(event.target.value)} minLength={2} maxLength={120} placeholder="문의 내용을 간단히 적어주세요." /></label>
              <label>문의 내용<textarea value={message} onChange={(event) => setMessage(event.target.value)} minLength={10} maxLength={2000} rows={6} placeholder="문제가 발생한 화면과 상황을 자세히 알려주시면 빠르게 확인할 수 있어요." /><small className="site-contact-form__count">{message.length}/2000</small></label>
              <p className="site-contact-form__notice">비밀번호, 인증번호, 주민등록번호 등 민감한 정보는 입력하지 마세요.</p>
              {error ? <p className="site-contact-form__error" role="alert">{error}</p> : null}
              <footer className="site-contact-form__actions">
                <button type="button" onClick={onClose}>취소</button>
                <button className="site-contact-form__submit" disabled={busy || !emailValid || subject.trim().length < 2 || message.trim().length < 10} type="submit">{busy ? '접수 중…' : '문의 접수하기'}</button>
              </footer>
            </form>
          )}
        </div>
      </section>
    </div>,
    document.body,
  );
}

function Footer({ footer, user }) {
  const [activeDetail, setActiveDetail] = useState(null);
  if (!footer) return null;

  const detail = activeDetail ? FOOTER_DETAILS[activeDetail] : null;

  return (
    <>
      <footer className="site-footer">
        <nav className="site-footer__links" aria-label="서비스 안내">
          {FOOTER_LINKS.map(([key, label]) => (
            <button type="button" key={key} onClick={() => setActiveDetail(key)}>{label}</button>
          ))}
        </nav>

        <div className="site-footer__contact">
          <strong>고객센터</strong>
          <a href={`mailto:${footer.supportEmail}`}>{footer.supportEmail}</a>
        </div>

        <div className="site-footer__brand">
          <Logo />
          <p>{footer.copyright}</p>
        </div>
      </footer>

      {detail ? <FooterModal detail={detail} onClose={() => setActiveDetail(null)} /> : null}
      {activeDetail === 'contact' ? <ContactModal user={user} onClose={() => setActiveDetail(null)} /> : null}
    </>
  );
}

export default Footer;
