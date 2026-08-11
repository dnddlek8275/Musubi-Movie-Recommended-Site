import { useEffect, useRef, useState } from 'react';

import { fetchSearchSuggestions } from '../../api.js';
import './headerFooter.css';
import Logo from './Logo.jsx';
import ThemeToggle from './ThemeToggle.jsx';

function Header({ navigation, onLogout, user }) {
  const [searchValue, setSearchValue] = useState(
    () => new URLSearchParams(window.location.search).get('keyword') || '',
  );
  const [suggestions, setSuggestions] = useState([]);
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [activeSuggestion, setActiveSuggestion] = useState(-1);
  const searchRef = useRef(null);
  const displayName = user?.nickname || user?.email || '';
  const fallbackNavigation = {
    authHref: '/login',
    authLabel: '로그인',
    menus: [
      { href: '/home', label: 'menu1' },
      { href: '/chat/group', label: 'menuw' },
      { href: '/recommendations', label: 'menu3' },
    ],
    searchPlaceholder: '',
  };
  const nav = navigation || fallbackNavigation;
  const menuItems = Array.isArray(nav.menus)
    ? nav.menus.map((menu, index) => ({
        href: menu.href || nav.menuHrefs?.[index],
        label: menu.label || menu,
      }))
    : [
        { href: nav.menu1Href, label: nav.menu1?.[0] || 'menu1' },
        { href: nav.menu2Href, label: nav.menu2?.[0] || 'menu2' },
        { href: nav.menu3Href, label: nav.menu3?.[0] || 'menu3' },
      ];

  useEffect(() => {
    const keyword = searchValue.trim();
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
  }, [searchValue]);

  useEffect(() => {
    const closeSuggestions = (event) => {
      if (!searchRef.current?.contains(event.target)) setSuggestionsOpen(false);
    };
    document.addEventListener('pointerdown', closeSuggestions);
    return () => document.removeEventListener('pointerdown', closeSuggestions);
  }, []);

  const openSearchResults = (keyword, type = '') => {
    const normalized = String(keyword || '').trim();
    if (!normalized) return;
    setSuggestionsOpen(false);
    const params = new URLSearchParams({ keyword: normalized });
    if (type) params.set('type', type);
    window.location.href = `/recommendations?${params.toString()}`;
  };

  const handleSearch = (event) => {
    event.preventDefault();
    const selected = activeSuggestion >= 0 ? suggestions[activeSuggestion] : null;
    openSearchResults(selected?.text || searchValue, selected?.type || '');
  };

  const handleSearchKeyDown = (event) => {
    if (!suggestionsOpen || suggestions.length === 0) {
      if (event.key === 'ArrowDown' && suggestions.length > 0) setSuggestionsOpen(true);
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveSuggestion((current) => (current + 1) % suggestions.length);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveSuggestion((current) => (current <= 0 ? suggestions.length - 1 : current - 1));
    } else if (event.key === 'Escape') {
      setSuggestionsOpen(false);
      setActiveSuggestion(-1);
    }
  };

  return (
    <header className="site-header" aria-label="상단 메뉴 영역">
      <a className="site-logo" href="/home" aria-label="Musubi 홈">
        <Logo />
      </a>

      <nav className="site-nav" aria-label="주 메뉴">
        {menuItems.map((menu) =>
          menu.href ? (
            <a className="site-nav__item" href={menu.href} key={menu.label}>
              {menu.label}
            </a>
          ) : (
            <span className="site-nav__item" key={menu.label}>
              {menu.label}
            </span>
          )
        )}

        {displayName ? (
          <a className="site-nav__item" href="/mypage">
            마이페이지
          </a>
        ) : null}

      </nav>

      <form
        className="site-search"
        aria-label="검색창"
        onSubmit={handleSearch}
        ref={searchRef}
      >
        <input
          className="site-search__text"
          type="text"
          name="search"
          placeholder={nav.searchPlaceholder}
          aria-label="검색어 입력"
          autoComplete="off"
          role="combobox"
          aria-autocomplete="list"
          aria-controls="site-search-suggestions"
          aria-expanded={suggestionsOpen && suggestions.length > 0}
          aria-activedescendant={activeSuggestion >= 0 ? `site-search-suggestion-${activeSuggestion}` : undefined}
          value={searchValue}
          onChange={(event) => {
            setSearchValue(event.target.value);
            setSuggestionsOpen(true);
          }}
          onFocus={() => setSuggestionsOpen(true)}
          onKeyDown={handleSearchKeyDown}
        />

        <button
          className="site-search__icon"
          type="submit"
          aria-label="검색"
        />

        {suggestionsOpen && searchValue.trim() && suggestions.length > 0 ? (
          <ul className="site-search__suggestions" id="site-search-suggestions" role="listbox">
            {suggestions.map((suggestion, index) => (
              <li key={`${suggestion.type}-${suggestion.text}`} role="presentation">
                <button
                  className={index === activeSuggestion ? 'is-active' : ''}
                  id={`site-search-suggestion-${index}`}
                  type="button"
                  role="option"
                  aria-selected={index === activeSuggestion}
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseEnter={() => setActiveSuggestion(index)}
                  onClick={() => openSearchResults(suggestion.text, suggestion.type)}
                >
                  <span>{suggestion.text}</span>
                  {suggestion.type ? <small>{suggestion.type}</small> : null}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </form>

      <div className="site-header__end">
        <ThemeToggle />

        {displayName ? (
          <div className="site-auth" aria-label="로그인 정보">
            <button
              className="site-auth__logout"
              onClick={onLogout}
              type="button"
            >
              Logout
            </button>
          </div>
        ) : (
          <a className="site-login" href={nav.authHref || '/login'}>
            {nav.authLabel || '로그인'}
          </a>
        )}
      </div>
    </header>
  );
}

export default Header;
