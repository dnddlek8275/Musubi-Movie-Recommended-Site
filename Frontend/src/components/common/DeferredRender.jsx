import { useEffect, useRef, useState } from 'react';

function DeferredRender({ children, minHeight = 320, rootMargin = '700px 0px' }) {
  const [visible, setVisible] = useState(false);
  const placeholderRef = useRef(null);

  useEffect(() => {
    if (visible) return undefined;
    if (!('IntersectionObserver' in window)) {
      setVisible(true);
      return undefined;
    }

    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      setVisible(true);
      observer.disconnect();
    }, { rootMargin });
    if (placeholderRef.current) observer.observe(placeholderRef.current);
    return () => observer.disconnect();
  }, [rootMargin, visible]);

  if (visible) return children;
  return (
    <div
      aria-hidden="true"
      ref={placeholderRef}
      style={{ minHeight, contentVisibility: 'auto', containIntrinsicSize: `auto ${minHeight}px` }}
    />
  );
}

export default DeferredRender;
