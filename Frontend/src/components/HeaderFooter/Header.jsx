import './headerFooter.css';
import Logo from './Logo.jsx';
import ThemeToggle from './ThemeToggle.jsx';

function Header({ navigation, onLogout, user }) {
  const displayName = user?.nickname || user?.email || '';
  const fallbackNavigation = {
    authHref: '/login',
    authLabel: 'Login',
    menus: [
      { href: '/chat/auto', label: 'menu1' },
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

  const handleSearch = (event) => {
    event.preventDefault();

    const keyword = event.currentTarget.search.value.trim();
    if (!keyword) return;

    window.location.href = `/recommendations?keyword=${encodeURIComponent(keyword)}`;
  };

  return (
    <header className="site-header" aria-label="상단 메뉴 영역">
      <a className="site-logo" href="/" aria-label="CineVerse 홈">
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
      >
        <input
          className="site-search__text"
          type="text"
          name="search"
          placeholder={nav.searchPlaceholder}
          aria-label="검색어 입력"
        />

        <button
          className="site-search__icon"
          type="submit"
          aria-label="검색"
        />
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
            {nav.authLabel || 'Login'}
          </a>
        )}
      </div>
    </header>
  );
}

export default Header;
