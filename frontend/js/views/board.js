import { api } from "/js/api.js?v=16";
import {
  ARCHIVE_STATUS,
  KANBAN_STATUS_ORDER,
  STATUS_LABELS,
  TASK_EDIT_STATUS_ORDER,
  escapeHtml,
  formatAuthor,
  formatDate,
  formatMemberChip,
  attachmentThumbHtml,
  descriptionFieldHtml,
  bindImagePicker,
  truncateText,
  normalizeStatus,
  showModal,
  showToast,
  toDatetimeLocal,
} from "/js/ui.js?v=16";
import { getTelegramUserId, haptic, showConfirm } from "/js/telegram.js?v=16";

export async function renderBoardPage(main, { boardId, navigate }) {
  main.innerHTML = `<div class="empty-state">Загрузка...</div>`;

  let data;
  try {
    data = await api.getBoard(boardId);
  } catch (e) {
    main.innerHTML = `<div class="empty-state">Ошибка: ${escapeHtml(e.message)}</div>`;
    return { title: "Доска" };
  }

  const { board, members, tasks } = data;

  const activeTasks = tasks.filter((t) => normalizeStatus(t.status) !== ARCHIVE_STATUS);
  const archivedTasks = tasks.filter((t) => normalizeStatus(t.status) === ARCHIVE_STATUS);

  const tasksByStatus = Object.fromEntries(KANBAN_STATUS_ORDER.map((s) => [s, []]));
  for (const t of activeTasks) {
    const status = normalizeStatus(t.status);
    tasksByStatus[status]?.push(t);
  }

  main.innerHTML = `
    <div class="section-header">
      <div class="section-title">Участники</div>
      <button class="section-add-btn" id="edit-members-btn" aria-label="Управление участниками">+</button>
    </div>
    <div class="members-list" id="members-list">
      ${members.map((m) => formatMemberChip(m.user)).join("")}
    </div>

    <div class="section-header">
      <div class="section-title">Задачи</div>
      <button class="section-add-btn" id="add-task-btn" aria-label="Добавить задачу">+</button>
    </div>
    <div class="kanban">
      ${KANBAN_STATUS_ORDER.map(
        (status) => `
        <div class="column" data-status="${status}">
          <div class="column-header">
            <span>${STATUS_LABELS[status]}</span>
            <span class="column-count">${tasksByStatus[status].length}</span>
          </div>
          ${tasksByStatus[status]
            .map((t) => renderTaskCard(t))
            .join("")}
        </div>`
      ).join("")}
    </div>
    <button class="btn btn-secondary" id="task-archive-btn" style="width:100%;margin-top:12px">
      Архив задач${archivedTasks.length ? ` (${archivedTasks.length})` : ""}
    </button>
  `;

  document.getElementById("edit-members-btn").onclick = () => {
    haptic();
    openEditMembers(board, members, boardId, main, () => navigate("board", { boardId }));
  };

  document.getElementById("add-task-btn").onclick = () => {
    haptic();
    openCreateTask(boardId, () => navigate("board", { boardId }));
  };

  document.getElementById("task-archive-btn").onclick = () => {
    haptic();
    openTaskArchive(archivedTasks, boardId, () => navigate("board", { boardId }));
  };

  main.querySelectorAll("[data-task-id]").forEach((el) => {
    el.addEventListener("click", () => {
      haptic();
      const task = tasks.find((t) => t.id === Number(el.dataset.taskId));
      openTaskModal(task, boardId, () => navigate("board", { boardId }));
    });
  });

  return { title: board.title };
}

function renderTaskCard(t) {
  const description = truncateText(t.description, 80);
  return `
    <div class="task-card" data-task-id="${t.id}">
      <div class="task-title">${escapeHtml(t.title)}</div>
      ${
        description
          ? `<div class="task-description">${escapeHtml(description)}</div>`
          : ""
      }
      ${
        t.deadline
          ? `<div class="task-deadline${isOverdue(t) ? " overdue" : ""}">⏰ ${formatDate(t.deadline)}</div>`
          : ""
      }
    </div>`;
}

function isOverdue(task) {
  const status = normalizeStatus(task.status);
  if (!task.deadline || status === "approved" || status === ARCHIVE_STATUS) return false;
  return new Date(task.deadline) < new Date();
}

function membersRowsHtml(memberList, board, canRemoveMembers) {
  if (!memberList.length) {
    return '<p style="color:var(--hint);font-size:13px">Нет участников</p>';
  }
  return memberList
    .map((m) => {
      const name = formatAuthor(m.user);
      const isOwner = m.user_id === board.owner_id;
      const removeBtn =
        canRemoveMembers && !isOwner
          ? `<button class="btn btn-danger btn-sm" data-remove-member="${m.id}">Удалить</button>`
          : "";
      return `
        <div class="member-row">
          <span>${escapeHtml(name)}${isOwner ? ' <span class="member-owner-badge">· владелец</span>' : ""}</span>
          ${removeBtn}
        </div>`;
    })
    .join("");
}

function updateMembersChips(container, memberList) {
  const list = container?.querySelector("#members-list");
  if (!list) return;
  list.innerHTML = memberList.map((m) => formatMemberChip(m.user)).join("");
}

function openEditMembers(board, members, boardId, main, onClose) {
  const canRemoveMembers = board.owner_id === getTelegramUserId();
  const buildModal = (memberList) => `
    <h2>Участники</h2>
    <div id="members-editor">${membersRowsHtml(memberList, board, canRemoveMembers)}</div>
    <div class="section-title" style="margin-top:16px">Добавить</div>
    <p style="color:var(--hint);font-size:13px;margin-bottom:12px">
      Пользователь должен хотя бы раз открыть mini app, чтобы его можно было добавить.
    </p>
    <div class="form-group">
      <label>Username в Telegram</label>
      <input type="text" id="member-username" placeholder="@username" />
    </div>
    <div class="modal-actions">
      <button class="btn btn-primary" id="add-member-submit">Добавить</button>
      <button class="btn btn-secondary" data-close>Готово</button>
    </div>
  `;

  const bindEditor = (modalEl, memberList) => {
    modalEl.querySelectorAll("[data-remove-member]").forEach((btn) => {
      btn.onclick = async () => {
        const memberId = Number(btn.dataset.removeMember);
        const member = memberList.find((item) => item.id === memberId);
        const ok = await showConfirm(`Удалить ${formatAuthor(member?.user)} из доски?`);
        if (!ok) return;
        try {
          await api.removeMember(boardId, memberId);
          haptic("medium");
          showToast("Участник удалён");
          const updated = await api.listMembers(boardId);
          modalEl.querySelector("#members-editor").innerHTML = membersRowsHtml(
            updated,
            board,
            canRemoveMembers
          );
          updateMembersChips(main, updated);
          bindEditor(modalEl, updated);
        } catch (err) {
          showToast(err.message);
        }
      };
    });

    modalEl.querySelector("#add-member-submit").onclick = async () => {
      const username = modalEl.querySelector("#member-username").value.trim();
      if (!username) return showToast("Введите username");
      try {
        await api.addMember(boardId, { username });
        haptic("medium");
        showToast("Участник добавлен");
        modalEl.querySelector("#member-username").value = "";
        const updated = await api.listMembers(boardId);
        modalEl.querySelector("#members-editor").innerHTML = membersRowsHtml(
          updated,
          board,
          canRemoveMembers
        );
        updateMembersChips(main, updated);
        bindEditor(modalEl, updated);
      } catch (err) {
        showToast(err.message);
      }
    };
  };

  const { modal } = showModal(buildModal(members), { onClose });
  bindEditor(modal, members);
}

function openCreateTask(boardId, onDone) {
  const { close } = showModal(`
    <h2>Новая задача</h2>
    <div class="form-group">
      <label>Название</label>
      <input type="text" id="task-title" maxlength="500" />
    </div>
    <div class="form-group">
      <label>Описание (необязательно)</label>
      ${descriptionFieldHtml({
        textareaId: "task-description",
        pickerId: "create-task-description-image",
        placeholder: "Детали задачи...",
      })}
    </div>
    <div class="form-group">
      <label>Статус</label>
      <select id="task-status" required>
        <option value="" disabled selected>Выберите статус</option>
        ${KANBAN_STATUS_ORDER.map((s) => `<option value="${s}">${STATUS_LABELS[s]}</option>`).join("")}
      </select>
    </div>
    <div class="form-group">
      <label>Дедлайн (необязательно)</label>
      <input type="datetime-local" id="task-deadline" />
    </div>
    <div class="modal-actions">
      <button class="btn btn-primary" id="create-task-btn">Создать</button>
      <button class="btn btn-secondary" data-close>Отмена</button>
    </div>
  `);

  const descImagePicker = bindImagePicker(
    document.querySelector('[data-image-picker="create-task-description-image"]')
  );

  document.getElementById("create-task-btn").onclick = async () => {
    const title = document.getElementById("task-title").value.trim();
    const status = document.getElementById("task-status").value;
    if (!title) return showToast("Введите название задачи");
    if (!status) return showToast("Выберите статус");
    const deadlineVal = document.getElementById("task-deadline").value;
    const description = document.getElementById("task-description").value.trim();
    const image = descImagePicker.getFile();
    const payload = { title, status };
    if (description) payload.description = description;
    if (deadlineVal) payload.deadline = new Date(deadlineVal).toISOString();
    try {
      await api.createTask(boardId, payload, { image });
      haptic("medium");
      showToast("Задача создана");
      close();
      onDone();
    } catch (err) {
      showToast(err.message);
    }
  };
}

function commentEditIconHtml() {
  return `
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>`;
}

function bindCommentActions(container, { task, boardId, onDone, commentsById }) {
  container.querySelectorAll("[data-delete-comment]").forEach((btn) => {
    btn.onclick = async () => {
      const commentId = Number(btn.dataset.deleteComment);
      const ok = await showConfirm("Удалить комментарий?");
      if (!ok) return;
      try {
        await api.deleteComment(task.id, commentId);
        haptic("medium");
        showToast("Комментарий удалён");
        openTaskModal(task, boardId, onDone);
      } catch (err) {
        showToast(err.message);
      }
    };
  });

  container.querySelectorAll("[data-edit-comment]").forEach((btn) => {
    btn.onclick = () => {
      const commentId = Number(btn.dataset.editComment);
      const commentEl = container.querySelector(`[data-comment-id="${commentId}"]`);
      if (!commentEl || commentEl.dataset.editing === "1") return;

      const comment = commentsById[commentId];
      if (!comment) return;

      commentEl.dataset.editing = "1";
      const view = commentEl.querySelector(".comment-view");
      view.classList.add("hidden");

      const textareaId = `edit-comment-text-${commentId}`;
      const pickerId = `edit-comment-image-${commentId}`;
      const editWrap = document.createElement("div");
      editWrap.className = "comment-edit";
      editWrap.innerHTML = `
        ${descriptionFieldHtml({
          textareaId,
          pickerId,
          value: comment.text,
          placeholder: "Комментарий...",
          compact: true,
        })}
        <div class="comment-edit-actions">
          <button type="button" class="btn btn-primary" data-save-comment="${commentId}">Сохранить</button>
          <button type="button" class="btn btn-secondary" data-cancel-comment="${commentId}">Отмена</button>
        </div>`;
      commentEl.appendChild(editWrap);

      const picker = bindImagePicker(
        editWrap.querySelector(`[data-image-picker="${pickerId}"]`),
        { existingUrl: comment.image_url || null }
      );

      editWrap.querySelector(`[data-cancel-comment="${commentId}"]`).onclick = () => {
        picker.destroy();
        openTaskModal(task, boardId, onDone);
      };

      editWrap.querySelector(`[data-save-comment="${commentId}"]`).onclick = async () => {
        const text = document.getElementById(textareaId).value.trim();
        const image = picker.getFile();
        const removeImage = picker.isExistingRemoved();
        const keepsExistingImage = Boolean(comment.image_url) && !removeImage && !image;
        if (!text && !image && !keepsExistingImage) {
          return showToast("Введите текст или выберите фото");
        }
        try {
          await api.updateComment(task.id, commentId, { text, image, removeImage });
          haptic("light");
          showToast("Комментарий обновлён");
          openTaskModal(task, boardId, onDone);
        } catch (err) {
          showToast(err.message);
        }
      };
    };
  });
}

async function openTaskModal(task, boardId, onDone) {
  let comments = [];
  try {
    comments = await api.listComments(task.id);
  } catch {
    /* ignore */
  }

  const taskStatus = normalizeStatus(task.status);
  const currentUserId = getTelegramUserId();
  const commentsById = Object.fromEntries(comments.map((c) => [c.id, c]));

  const renderComment = (c) => {
    const author = formatAuthor(c.user);
    const canManage = currentUserId != null && c.user_id === currentUserId;
    const editBtn = canManage
      ? `<button type="button" class="comment-action-btn" data-edit-comment="${c.id}" aria-label="Редактировать комментарий">${commentEditIconHtml()}</button>`
      : "";
    const deleteBtn = canManage
      ? `<button type="button" class="comment-action-btn comment-delete-btn" data-delete-comment="${c.id}" aria-label="Удалить комментарий">×</button>`
      : "";
    const actions = canManage ? `<div class="comment-actions">${editBtn}${deleteBtn}</div>` : "";
    const editedLabel = c.edited_at ? `<span class="comment-edited"> · отредактировано</span>` : "";
    const image = attachmentThumbHtml(c.image_url);
    const text = c.text ? `<div class="comment-text">${escapeHtml(c.text)}</div>` : "";
    return `
      <div class="comment" data-comment-id="${c.id}">
        <div class="comment-header">
          <div class="comment-meta">${escapeHtml(author)} · ${formatDate(c.created_at)}${editedLabel}</div>
          ${actions}
        </div>
        <div class="comment-view">
          ${text}
          ${image}
        </div>
      </div>`;
  };

  const { close, modal: m } = showModal(`
    <div class="modal-header">
      <h2>Задача</h2>
      <button type="button" class="modal-delete-btn" id="delete-task" aria-label="Удалить задачу">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m2 0v12a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V7h12z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M10 11v6M14 11v6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        </svg>
      </button>
    </div>
    <div class="form-group">
      <label>Название</label>
      <input type="text" id="edit-task-title" value="${escapeHtml(task.title)}" maxlength="500" />
    </div>
    <div class="form-group">
      <label>Описание</label>
      ${descriptionFieldHtml({
        textareaId: "edit-task-description",
        pickerId: "edit-task-description-image",
        value: task.description || "",
        placeholder: "Детали задачи...",
      })}
    </div>
    <div class="form-group">
      <label>Статус</label>
      <select id="edit-task-status">
        ${TASK_EDIT_STATUS_ORDER.map(
          (s) =>
            `<option value="${s}"${taskStatus === s ? " selected" : ""}>${STATUS_LABELS[s]}</option>`
        ).join("")}
      </select>
    </div>
    <div class="form-group">
      <label>Дедлайн</label>
      <input type="datetime-local" id="edit-task-deadline" value="${toDatetimeLocal(task.deadline)}" />
    </div>
    <div class="modal-actions">
      <button class="btn btn-primary" id="save-task">Сохранить</button>
    </div>

    <div class="comments">
      <div class="section-title">Комментарии</div>
      <div id="comments-list">
        ${
          comments.length
            ? comments.map(renderComment).join("")
            : '<p style="color:var(--hint);font-size:13px">Пока нет комментариев</p>'
        }
      </div>
      <div class="form-group" style="margin-top:12px">
        ${descriptionFieldHtml({
          textareaId: "new-comment",
          pickerId: "comment-image",
          placeholder: "Написать комментарий...",
          compact: true,
        })}
      </div>
      <button class="btn btn-secondary" id="add-comment-btn" style="width:100%">Отправить</button>
    </div>
    <button class="btn btn-secondary" data-close style="width:100%;margin-top:12px">Закрыть</button>
  `);

  const descImagePicker = bindImagePicker(
    m.querySelector('[data-image-picker="edit-task-description-image"]'),
    { existingUrl: task.description_image_url }
  );
  const commentImagePicker = bindImagePicker(m.querySelector('[data-image-picker="comment-image"]'));

  m.querySelector("#save-task").onclick = async () => {
    const title = document.getElementById("edit-task-title").value.trim();
    const status = document.getElementById("edit-task-status").value;
    const deadlineVal = document.getElementById("edit-task-deadline").value;
    const description = document.getElementById("edit-task-description").value.trim();
    const image = descImagePicker.getFile();
    const payload = { title, status, description: description || null };
    payload.deadline = deadlineVal ? new Date(deadlineVal).toISOString() : null;
    try {
      await api.updateTask(task.id, payload, {
        image,
        removeImage: descImagePicker.isExistingRemoved(),
      });
      haptic("medium");
      showToast("Задача обновлена");
      close();
      onDone();
    } catch (err) {
      showToast(err.message);
    }
  };

  m.querySelector("#delete-task").onclick = async () => {
    const ok = await showConfirm("Удалить эту задачу?");
    if (!ok) return;
    try {
      await api.deleteTask(task.id);
      haptic("heavy");
      showToast("Задача удалена");
      close();
      onDone();
    } catch (err) {
      showToast(err.message);
    }
  };

  m.querySelector("#add-comment-btn").onclick = async () => {
    const text = document.getElementById("new-comment").value.trim();
    const image = commentImagePicker.getFile();
    if (!text && !image) return showToast("Введите текст или выберите фото");
    try {
      await api.addComment(task.id, { text, image });
      haptic("light");
      showToast("Комментарий добавлен");
      openTaskModal(task, boardId, onDone);
    } catch (err) {
      showToast(err.message);
    }
  };

  bindCommentActions(m, { task, boardId, onDone, commentsById });
}

function openTaskArchive(archivedTasks, boardId, onDone) {
  const { close, modal } = showModal(`
    <h2>Архив задач</h2>
    ${
      archivedTasks.length
        ? `<div class="task-archive-list">${archivedTasks.map((t) => renderTaskCard(t)).join("")}</div>`
        : '<p class="empty-state" style="padding:16px 0">В архиве пока нет задач</p>'
    }
    <button class="btn btn-secondary" data-close style="width:100%;margin-top:12px">Закрыть</button>
  `);

  modal.querySelectorAll("[data-task-id]").forEach((el) => {
    el.onclick = () => {
      haptic();
      const task = archivedTasks.find((t) => t.id === Number(el.dataset.taskId));
      close();
      openTaskModal(task, boardId, onDone);
    };
  });
}
