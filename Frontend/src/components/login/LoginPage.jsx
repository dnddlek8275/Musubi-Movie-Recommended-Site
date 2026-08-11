import IntroPage from '../intro/IntroPage.jsx';

function LoginPage({ onGuest, onLogin }) {
  return <IntroPage initialScene={4} onLogin={onLogin} onStart={onGuest} />;
}

export default LoginPage;
