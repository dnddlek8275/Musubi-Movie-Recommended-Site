import './loadingSkeleton.css';

export function SkeletonBlock({ className = '', ...props }) {
  return <span className={`loading-skeleton${className ? ` ${className}` : ''}`} {...props} />;
}

export function PosterRowSkeleton({ count = 7, compact = false, className = '' }) {
  return (
    <div className={`loading-poster-row${compact ? ' is-compact' : ''}${className ? ` ${className}` : ''}`} aria-hidden="true">
      {Array.from({ length: count }, (_, index) => (
        <div className="loading-poster-card" key={index}>
          <SkeletonBlock className="loading-skeleton--poster" />
          <SkeletonBlock className="loading-skeleton--line loading-skeleton--title" />
          <SkeletonBlock className="loading-skeleton--line loading-skeleton--short" />
        </div>
      ))}
    </div>
  );
}

export function PanelSkeleton({ lines = 3, className = '' }) {
  return (
    <div className={`loading-panel${className ? ` ${className}` : ''}`} aria-hidden="true">
      <SkeletonBlock className="loading-skeleton--heading" />
      {Array.from({ length: lines }, (_, index) => (
        <SkeletonBlock
          className={`loading-skeleton--line${index === lines - 1 ? ' loading-skeleton--short' : ''}`}
          key={index}
        />
      ))}
    </div>
  );
}

export default SkeletonBlock;
