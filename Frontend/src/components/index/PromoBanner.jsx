import imageData from '../../imgData.json';

function PromoBanner() {
  const promos = imageData.hero?.promos || [];

  return (
    <article className="index-hero-card">
      <div className="index-hero-slider">
        {promos.map((promo) => (
          <a
            className="index-hero-slide"
            href={promo.link}
            target="_blank"
            rel="noreferrer"
            key={promo.id}
          >
            <img src={promo.image} alt={promo.title} />
          </a>
        ))}
      </div>
    </article>
  );
}

export default PromoBanner;
