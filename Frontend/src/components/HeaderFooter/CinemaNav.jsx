import { useEffect, useRef, useState } from 'react';

import { checkAdminAccess, fetchSearchSuggestions } from '../../api.js';
import { navigateTo } from '../../navigation.js';
import Logo from './Logo.jsx';
import ThemeToggle from './ThemeToggle.jsx';
import './headerFooter.css';

function CinemaSearch() {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [activeSuggestion, setActiveSuggestion] = useState(-1);
  const searchRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const timer = window.setTimeout(() => inputRef.current?.focus(), 180);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    const keyword = value.trim();
    if (!keyword) {
      setSuggestions([]);
      setActiveSuggestion(-1);
      return undefined;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      fetchSearchSuggestions(controller.signal, keyword, 8)
        .then((items) => {
          setSuggestions(items);
          setActiveSuggestion(-1);
        })
        .catch((error) => {
          if (error.name !== 'AbortError') setSuggestions([]);
        });
    }, 140);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [value]);

  useEffect(() => {
    const closeSearch = (event) => {
      if (!searchRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener('pointerdown', closeSearch);
    return () => document.removeEventListener('pointerdown', closeSearch);
  }, []);

  const openResults = (keyword, type = '') => {
    const normalized = String(keyword || '').trim();
    if (!normalized) return;
    const params = new URLSearchParams({ keyword: normalized });
    if (type) params.set('type', type);
    navigateTo(`/recommendations?${params.toString()}`);
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!open) {
      setOpen(true);
      return;
    }
    const selected = activeSuggestion >= 0 ? suggestions[activeSuggestion] : null;
    openResults(selected?.text || value, selected?.type || '');
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Escape') {
      setOpen(false);
      setActiveSuggestion(-1);
      return;
    }
    if (suggestions.length === 0) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveSuggestion((current) => (current + 1) % suggestions.length);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveSuggestion((current) => (current <= 0 ? suggestions.length - 1 : current - 1));
    }
  };

  return (
    <form
      className={`home3-cinema-search${open ? ' is-open' : ''}`}
      onSubmit={handleSubmit}
      ref={searchRef}
      role="search"
    >
      <button className="home3-cinema-search__button" type="submit" aria-label={open ? '영화 검색' : '검색창 열기'}>
        <svg aria-hidden="true" viewBox="0 0 24 24">
          <circle cx="11" cy="11" r="6.5" />
          <path d="m16 16 4 4" />
        </svg>
      </button>
      <input
        aria-label="영화 검색어 입력"
        autoComplete="off"
        placeholder="영화, 배우, 장르 검색"
        ref={inputRef}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
      />
      {open && value.trim() && suggestions.length > 0 ? (
        <ul className="home3-cinema-search__suggestions" role="listbox">
          {suggestions.map((suggestion, index) => (
            <li key={`${suggestion.type}-${suggestion.text}`}>
              <button
                className={index === activeSuggestion ? 'is-active' : ''}
                type="button"
                role="option"
                aria-selected={index === activeSuggestion}
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => setActiveSuggestion(index)}
                onClick={() => openResults(suggestion.text, suggestion.type)}
              >
                <span>{suggestion.text}</span>
                {suggestion.type ? <small>{suggestion.type}</small> : null}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </form>
  );
}

function CinemaNav({ authUser, onLogout, overlay = false }) {
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    if (!authUser) {
      setIsAdmin(false);
      return undefined;
    }

    const controller = new AbortController();
    checkAdminAccess(controller.signal)
      .then((response) => setIsAdmin(Boolean(response.data?.is_admin)))
      .catch((error) => {
        if (error.name !== 'AbortError') setIsAdmin(false);
      });
    return () => controller.abort();
  }, [authUser?.email]);

  return (
    <header className={`home3-cinema-nav${overlay ? '' : ' cinema-page-nav'}`}>
      <a className="home3-cinema-nav__logo" href="/home" aria-label="Musubi 홈"><Logo /></a>
      <nav aria-label="주요 이동 메뉴">
        <a href="/home">홈</a>
        <a href="/recommendations">박스오피스</a>
        <a href="/chat/group">캐릭터와 대화</a>
        {authUser ? <a href="/mypage">마이페이지</a> : null}
        <CinemaSearch />
      </nav>
      <div className="home3-cinema-nav__actions">
        {isAdmin ? (
          <a className="cinema-nav__admin" href="/admin" aria-label="관리자 페이지">
            <svg aria-hidden="true" viewBox="0 0 24 24">
              <path d="M12 3.5 19 6v5.4c0 4.3-2.8 7.5-7 9.1-4.2-1.6-7-4.8-7-9.1V6l7-2.5Z" />
              <path d="M9 12.2 11.1 14 15.3 9.8" />
            </svg>
            <span>관리자</span>
          </a>
        ) : null}
        {authUser && onLogout ? (
          <button className="cinema-nav__logout" type="button" onClick={onLogout}>
            <svg aria-hidden="true" viewBox="0 0 24 24">
              <path d="M10 5H6.5A1.5 1.5 0 0 0 5 6.5v11A1.5 1.5 0 0 0 6.5 19H10" />
              <path d="M14 8l4 4-4 4M18 12H9" />
            </svg>
            <span>로그아웃</span>
          </button>
        ) : (
          <a className="cinema-nav__logout cinema-nav__login" href="/login">
            <svg aria-hidden="true" viewBox="0 0 24 24">
              <path d="M14 5h3.5A1.5 1.5 0 0 1 19 6.5v11a1.5 1.5 0 0 1-1.5 1.5H14" />
              <path d="M10 8l4 4-4 4M14 12H5" />
            </svg>
            <span>로그인</span>
          </a>
        )}
        <ThemeToggle />
      </div>
    </header>
  );
}

export default CinemaNav;
