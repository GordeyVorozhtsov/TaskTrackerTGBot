const tg = window.Telegram?.WebApp;

export function initTelegram() {
  if (!tg) return;

  tg.ready();
  tg.expand();
}

export function getInitData() {
  return tg?.initData || "";
}

export function isDevMode() {
  return !getInitData() && (location.hostname === "localhost" || location.hostname === "127.0.0.1");
}

export function getTelegramUserId() {
  if (isDevMode()) return 123456789;
  return tg?.initDataUnsafe?.user?.id ?? null;
}

export function haptic(type = "light") {
  tg?.HapticFeedback?.impactOccurred(type);
}

export function showConfirm(message) {
  return new Promise((resolve) => {
    if (tg?.showConfirm) {
      tg.showConfirm(message, resolve);
    } else {
      resolve(window.confirm(message));
    }
  });
}
