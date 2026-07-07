import { initTelegram, haptic } from "/js/telegram.js?v=16";
import { initTheme } from "/js/theme.js?v=16";
import { renderBoardsPage, openCreateBoardModal } from "/js/views/boards.js?v=16";
import { renderBoardPage } from "/js/views/board.js?v=16";
import { escapeHtml } from "/js/ui.js?v=16";

const header = document.getElementById("header");
const backBtn = document.getElementById("back-btn");
const pageTitle = document.getElementById("page-title");
const themeBtn = document.getElementById("theme-btn");
const headerAction = document.getElementById("header-action");
const main = document.getElementById("main");

const state = {
  view: "boards",
  boardId: null,
};

function showFatalError(error) {
  console.error(error);
  header?.classList.remove("hidden");
  if (pageTitle) pageTitle.textContent = "Ошибка";
  if (main) {
    main.innerHTML = `<div class="empty-state">Не удалось загрузить приложение:<br>${escapeHtml(error?.message || String(error))}</div>`;
  }
}

function navigate(view, params = {}) {
  state.view = view;
  state.boardId = params.boardId ?? null;
  render();
}

async function render() {
  if (!header || !main) {
    throw new Error("DOM elements not found");
  }

  header.classList.remove("hidden");

  if (state.view === "boards") {
    pageTitle.textContent = "Доски";
    backBtn.classList.add("hidden");
    themeBtn?.classList.remove("hidden");
    headerAction.classList.remove("hidden");
    headerAction.textContent = "+";
    headerAction.onclick = () => openCreateBoardModal(() => navigate("boards"));
    await renderBoardsPage(main, { navigate });
  } else if (state.view === "board") {
    backBtn.classList.remove("hidden");
    backBtn.onclick = () => navigate("boards");
    themeBtn?.classList.add("hidden");
    headerAction.classList.add("hidden");
    const result = await renderBoardPage(main, { boardId: state.boardId, navigate });
    pageTitle.textContent = result?.title || "Доска";
  }
}

async function boot() {
  try {
    initTelegram();
    initTheme(themeBtn, { onToggle: () => haptic("light") });
    await render();
  } catch (error) {
    showFatalError(error);
  }
}

window.addEventListener("unhandledrejection", (event) => {
  showFatalError(event.reason);
});

boot();
