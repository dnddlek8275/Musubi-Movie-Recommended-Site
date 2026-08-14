import Footer from './components/HeaderFooter/Footer.jsx';
import CinemaNav from './components/HeaderFooter/CinemaNav.jsx';

function DefaultLayout({ authUser, children, footer, isHomeArriving = false, navigation, onLogout }) {
  const isHome = window.location.pathname === '/home';
  return (
    <div className={`app-shell${isHomeArriving ? ' is-arriving-from-onboarding' : ''}`}>
      <div className={`page ${isHome ? 'has-home-nav' : 'has-cinema-nav'}`}>
        <CinemaNav authUser={authUser} onLogout={onLogout} overlay={isHome} />

        {children}

        <Footer footer={footer} user={authUser} />
      </div>
    </div>
  );
}

export default DefaultLayout;
