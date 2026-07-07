import { api } from "/js/api.js?v=16";
import { escapeHtml, showModal, showToast } from "/js/ui.js?v=16";
import { getTelegramUserId, haptic, showConfirm } from "/js/telegram.js?v=16";

export async function renderBoardsPage(main, { navigate }) {
  main.innerHTML = `<div class="empty-state">Загрузка...</div>`;

  let boards;
  try {
    boards = await api.listBoards();
  } catch (e) {
    main.innerHTML = `<div class="empty-state">Ошибка: ${escapeHtml(e.message)}</div>`;
    return;
  }

  if (!boards.length) {
    main.innerHTML = `
      <div class="empty-state">
        <p>У вас пока нет досок</p>
        <p style="margin-top:8px">Нажмите + чтобы создать первую</p>
      </div>`;
    return;
  }

  const currentUserId = getTelegramUserId();

  main.innerHTML = boards
    .map(
      (b) => `
    <div class="card" data-board-id="${b.id}">
      <div class="card-row">
        <span class="card-title">${escapeHtml(b.title)}</span>
        ${
          b.owner_id === currentUserId
            ? `<div class="dropdown-wrap">
          <button class="menu-btn" data-menu="${b.id}" aria-label="Меню">⋯</button>
        </div>`
            : ""
        }
      </div>
    </div>`
    )
    .join("");

  main.querySelectorAll("[data-board-id]").forEach((card) => {
    card.addEventListener("click", (e) => {
      if (e.target.closest("[data-menu]")) return;
      haptic();
      navigate("board", { boardId: Number(card.dataset.boardId) });
    });
  });

  main.querySelectorAll("[data-menu]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      haptic();
      const boardId = Number(btn.dataset.menu);
      const board = boards.find((b) => b.id === boardId);
      openBoardMenu(board, () => navigate("boards"));
    });
  });
}

function openBoardMenu(board, onChanged) {
  const isOwner = board.owner_id === getTelegramUserId();
  const ownerActions = isOwner
    ? `
      <button class="btn btn-secondary" id="edit-board">Редактировать название</button>
      <button class="btn btn-danger" id="delete-board">Удалить доску</button>`
    : "";

  const { modal: m } = showModal(`
    <h2>${escapeHtml(board.title)}</h2>
    <div class="modal-actions">
      ${ownerActions}
    </div>
  `);

  if (!isOwner) return;

  m.querySelector("#edit-board").onclick = () => {
    showModal(`
      <h2>Новое название</h2>
      <div class="form-group">
        <input type="text" id="board-title" value="${escapeHtml(board.title)}" maxlength="255" />
      </div>
      <div class="modal-actions">
        <button class="btn btn-primary" id="save-board">Сохранить</button>
        <button class="btn btn-secondary" data-close>Отмена</button>
      </div>
    `);
    document.getElementById("save-board").onclick = async () => {
      const title = document.getElementById("board-title").value.trim();
      if (!title) return showToast("Введите название");
      try {
        await api.updateBoard(board.id, title);
        haptic("medium");
        showToast("Доска обновлена");
        onChanged();
      } catch (err) {
        showToast(err.message);
      }
    };
  };

  m.querySelector("#delete-board").onclick = async () => {
    const ok = await showConfirm(`Удалить доску «${board.title}»? Это действие необратимо.`);
    if (!ok) return;
    try {
      await api.deleteBoard(board.id);
      haptic("heavy");
      showToast("Доска удалена");
      onChanged();
    } catch (err) {
      showToast(err.message);
    }
  };
}

export function openCreateBoardModal(onCreated) {
  showModal(`
    <h2>Новая доска</h2>
    <div class="form-group">
      <label>Название</label>
      <input type="text" id="new-board-title" placeholder="Например: Проект Alpha" maxlength="255" />
    </div>
    <div class="modal-actions">
      <button class="btn btn-primary" id="create-board-btn">Создать</button>
      <button class="btn btn-secondary" data-close>Отмена</button>
    </div>
  `);

  const input = document.getElementById("new-board-title");
  input.focus();

  document.getElementById("create-board-btn").onclick = async () => {
    const title = input.value.trim();
    if (!title) return showToast("Введите название");
    try {
      await api.createBoard(title);
      haptic("medium");
      showToast("Доска создана");
      onCreated();
    } catch (err) {
      showToast(err.message);
    }
  };
}
