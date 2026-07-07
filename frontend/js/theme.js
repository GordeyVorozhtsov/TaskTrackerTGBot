const STORAGE_KEY = "tt-theme";

const THEME_COLORS = {
  light: { bg: "#f2f2f7", header: "#f2f2f7" },
  dark: { bg: "#1c1c1e", header: "#1c1c1e" },
};

/** In-memory source of truth — Telegram WebView often blocks localStorage. */
let currentTheme = null;

function normalizeTheme(value) {
  return value === "light" ? "light" : "dark";
}

function readLocalTheme() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    /* localStorage unavailable in some WebViews */
  }
  return "dark";
}

function writeLocalTheme(theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    /* ignore */
  }
}

function readCloudTheme(callback) {
  const cloud = window.Telegram?.WebApp?.CloudStorage;
  if (!cloud) {
    callback(null);
    return;
  }
  try {
    cloud.getItem(STORAGE_KEY, (err, value) => {
      if (!err && (value === "light" || value === "dark")) {
        callback(value);
      } else {
        callback(null);
      }
    });
  } catch {
    callback(null);
  }
}

function writeCloudTheme(theme) {
  const cloud = window.Telegram?.WebApp?.CloudStorage;
  if (!cloud) return;
  try {
    cloud.setItem(STORAGE_KEY, theme, () => {});
  } catch {
    /* ignore */
  }
}

export function getTheme() {
  if (currentTheme) return currentTheme;
  return readLocalTheme();
}

export function getThemeIcon(theme = getTheme()) {
  return theme === "light" ? "🌙" : "☀️";
}

export function applyTheme(theme) {
  const normalized = normalizeTheme(theme);
  document.documentElement.dataset.theme = normalized;

  const btn = document.getElementById("theme-btn");
  if (btn) btn.textContent = getThemeIcon(normalized);

  const colors = THEME_COLORS[normalized];
  const tg = window.Telegram?.WebApp;
  if (tg && colors) {
    tg.setHeaderColor(colors.header);
    tg.setBackgroundColor(colors.bg);
  }
}

export function setTheme(theme) {
  currentTheme = normalizeTheme(theme);
  writeLocalTheme(currentTheme);
  writeCloudTheme(currentTheme);
  applyTheme(currentTheme);
}

export function toggleTheme() {
  const next = getTheme() === "dark" ? "light" : "dark";
  setTheme(next);
  return next;
}

function loadPersistedTheme(onReady) {
  currentTheme = readLocalTheme();
  applyTheme(currentTheme);

  readCloudTheme((cloudTheme) => {
    if (cloudTheme && cloudTheme !== currentTheme) {
      currentTheme = cloudTheme;
      writeLocalTheme(currentTheme);
      applyTheme(currentTheme);
    }
    onReady?.(currentTheme);
  });
}

export function initTheme(themeBtn, { onToggle } = {}) {
  if (themeBtn && !themeBtn.dataset.themeBound) {
    themeBtn.dataset.themeBound = "1";
    themeBtn.type = "button";
    themeBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      onToggle?.();
      toggleTheme();
    });
  }

  loadPersistedTheme();
}
