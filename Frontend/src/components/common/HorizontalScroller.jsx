import { useCallback, useEffect, useRef, useState } from 'react';

import './horizontalScroller.css';

function HorizontalScroller({
  children,
  className = '',
  ariaLabel,
  externalRef = null,
  railProps = {},
  scrollRatio = 0.82,
  onReachEnd = null,
}) {
  const internalRef = useRef(null);
  const [state, setState] = useState({ back: false, forward: false });

  const setRailRef = useCallback((node) => {
    internalRef.current = node;
    if (externalRef && typeof externalRef === 'object') externalRef.current = node;
    if (typeof externalRef === 'function') externalRef(node);
  }, [externalRef]);

  const update = useCallback(() => {
    const rail = internalRef.current;
    if (!rail) return;
    const max = Math.max(rail.scrollWidth - rail.clientWidth, 0);
    setState({ back: rail.scrollLeft > 4, forward: rail.scrollLeft < max - 4 });
    if (onReachEnd && max > 0 && max - rail.scrollLeft <= Math.max(120, rail.clientWidth * 0.12)) {
      onReachEnd();
    }
  }, [onReachEnd]);

  useEffect(() => {
    const rail = internalRef.current;
    if (!rail) return undefined;
    const frame = window.requestAnimationFrame(update);
    const observer = new ResizeObserver(update);
    observer.observe(rail);
    Array.from(rail.children).forEach((child) => observer.observe(child));
    window.addEventListener('resize', update);
    return () => {
      window.cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener('resize', update);
    };
  }, [children, update]);

  const scroll = (direction) => {
    const rail = internalRef.current;
    if (!rail) return;
    rail.scrollBy({
      left: direction * Math.max(rail.clientWidth * scrollRatio, 280),
      behavior: 'smooth',
    });
  };

  const { onScroll, ...otherRailProps } = railProps;

  return (
    <div className={`horizontal-scroller${state.back ? ' has-prev' : ''}${state.forward ? ' has-next' : ''}`}>
      {state.back ? (
        <button className="horizontal-scroller__arrow is-prev" type="button" onClick={() => scroll(-1)} aria-label="이전 영화 보기">‹</button>
      ) : null}
      <div
        {...otherRailProps}
        aria-label={ariaLabel}
        className={className}
        onScroll={(event) => { update(); onScroll?.(event); }}
        ref={setRailRef}
      >
        {children}
      </div>
      {state.forward ? (
        <button className="horizontal-scroller__arrow is-next" type="button" onClick={() => scroll(1)} aria-label="다음 영화 보기">›</button>
      ) : null}
    </div>
  );
}

export default HorizontalScroller;
