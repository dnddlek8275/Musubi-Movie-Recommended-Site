function Logo() {
  return (
    <span className="site-logo__art" aria-hidden="true">
      <img
        className="site-logo__image site-logo__image--dark"
        src="/images/brand/musubi-logo-dark.webp"
        decoding="async"
        alt=""
      />
      <img
        className="site-logo__image site-logo__image--light"
        src="/images/brand/musubi-logo.webp"
        decoding="async"
        alt=""
      />
    </span>
  );
}

export default Logo;
