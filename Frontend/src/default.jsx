import Footer from './components/HeaderFooter/Footer.jsx';
import Header from './components/HeaderFooter/Header.jsx';

function DefaultLayout({ authUser, children, footer, isHomeArriving = false, navigation, onLogout }) {
  return (
    <div className={`app-shell${isHomeArriving ? ' is-arriving-from-onboarding' : ''}`}>
      <div className="page">
        <Header
          navigation={navigation}
          onLogout={onLogout}
          user={authUser}
        />

        {children}

        <Footer footer={footer} user={authUser} />
      </div>
    </div>
  );
}

export default DefaultLayout;
