import imageData from '../../imgData.json';

function PromoBanner({ highResolution = false }) {
  const promos = highResolution
    ? imageData.homeHero?.promos || imageData.hero?.promos || []
    : imageData.hero?.promos || [];
  const slides = promos.length > 0
    ? [...promos, { ...promos[0], id: `${promos[0].id}-clone`, isClone: true }]
    : [];

  return (
    <article className="index-hero-card">
      <div className={`index-hero-slider${promos.length === 12 ? ' index-hero-slider--12' : ''}`}>
        {slides.map((promo, index) => {
          const imageSource = highResolution
            ? promo.highResolutionImage || promo.image
            : promo.image;
          const image = (
            <img
              src={imageSource}
              alt={promo.isClone ? '' : promo.title}
              decoding="async"
              fetchPriority={index === 0 ? 'high' : 'auto'}
              loading={index === 0 ? 'eager' : 'lazy'}
            />
          );

          return promo.link ? (
            <a
              aria-hidden={promo.isClone || undefined}
              className="index-hero-slide"
              href={promo.link}
              tabIndex={promo.isClone ? -1 : undefined}
              key={promo.id}
            >
              {image}
            </a>
          ) : (
            <div
              aria-hidden={promo.isClone || undefined}
              className="index-hero-slide"
              key={promo.id}
            >
              {image}
            </div>
          );
        })}
      </div>
    </article>
  );
}

export default PromoBanner;
