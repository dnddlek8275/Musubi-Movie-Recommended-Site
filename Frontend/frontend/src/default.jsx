import Footer from './components/HeaderFooter/Footer.jsx';
import Header from './components/HeaderFooter/Header.jsx';

function DefaultLayout({ authUser, children, footer, navigation, onLogout }) {
  return (
    <div className="app-shell">
      <div className="page">
        <Header
          navigation={navigation}
          onLogout={onLogout}
          user={authUser}
        />

        {children}

        <Footer footer={footer} />
      </div>
    </div>
  );
}

export default DefaultLayout;
