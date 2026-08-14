export const NAVIGATION_EVENT = 'musubi:navigation';

function updateLocation(target, replace) {
  const url = new URL(target, window.location.href);
  if (url.origin !== window.location.origin) {
    window.location.assign(url.href);
    return;
  }

  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  const next = `${url.pathname}${url.search}${url.hash}`;
  if (current === next) return;

  window.history[replace ? 'replaceState' : 'pushState']({}, '', next);
  window.dispatchEvent(new CustomEvent(NAVIGATION_EVENT, { detail: { href: next } }));
}

export function navigateTo(target) {
  updateLocation(target, false);
}

export function replaceTo(target) {
  updateLocation(target, true);
}
