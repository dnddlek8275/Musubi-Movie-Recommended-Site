function Footer({ footer }) {
  if (!footer) return null;

  return (
    <footer className="site-footer">
      <div className="site-footer__contact">
        <p>{footer.email}</p>
        <p>{footer.phone}</p>
        <p>{footer.privacy}</p>
      </div>

      <p className="site-footer__copyright">{footer.copyright}</p>

      <div aria-hidden="true" />
    </footer>
  );
}

export default Footer;
