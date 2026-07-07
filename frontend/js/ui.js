const overlay = document.getElementById("modal-overlay");
const modal = document.getElementById("modal");
const toastEl = document.getElementById("toast");

let toastTimer;

export function showToast(message, duration = 2500) {
  toastEl.textContent = message;
  toastEl.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.add("hidden"), duration);
}

export function showModal(contentHtml, { onClose } = {}) {
  modal.innerHTML = contentHtml;
  overlay.classList.remove("hidden");

  const close = () => {
    overlay.classList.add("hidden");
    modal.innerHTML = "";
    onClose?.();
  };

  overlay.onclick = (e) => {
    if (e.target === overlay) close();
  };

  modal.querySelectorAll("[data-close]").forEach((el) => {
    el.addEventListener("click", close);
  });

  return { close, modal };
}

export function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function truncateText(text, maxLength = 80) {
  if (!text) return "";
  const trimmed = String(text).trim();
  if (trimmed.length <= maxLength) return trimmed;
  return `${trimmed.slice(0, maxLength).trimEnd()}…`;
}

export function attachmentThumbHtml(url, alt = "Изображение") {
  if (!url) return "";
  return `
    <a class="attachment-thumb" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">
      <img src="${escapeHtml(url)}" alt="${escapeHtml(alt)}" />
    </a>`;
}

export function descriptionFieldHtml({
  textareaId,
  pickerId,
  value = "",
  placeholder = "",
  compact = false,
}) {
  const compactClass = compact ? " rich-field--compact" : "";
  return `
    <div class="rich-field${compactClass}" data-image-picker="${escapeHtml(pickerId)}">
      <textarea
        id="${escapeHtml(textareaId)}"
        class="rich-field-text"
        maxlength="5000"
        placeholder="${escapeHtml(placeholder)}"
      >${escapeHtml(value)}</textarea>
      <div class="rich-field-bar">
        <div class="rich-field-thumb hidden">
          <img class="image-picker-preview" alt="" />
          <button type="button" class="image-picker-remove hidden" aria-label="Удалить фото">×</button>
        </div>
        <button type="button" class="image-picker-add" aria-label="Добавить фото">+</button>
      </div>
      <input type="file" class="image-picker-input" accept="image/*" hidden />
    </div>`;
}

export function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function toDatetimeLocal(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export const STATUS_LABELS = {
  new: "Новая",
  in_work: "В работе",
  on_approval: "На согласовании",
  revisions: "Правки",
  approved: "Согласована",
  archive: "Архив",
};

export const ARCHIVE_STATUS = "archive";

/** Статусы колонок канбана (без архива). */
export const KANBAN_STATUS_ORDER = ["new", "in_work", "on_approval", "revisions", "approved"];

/** Все статусы для редактирования задачи. */
export const TASK_EDIT_STATUS_ORDER = [...KANBAN_STATUS_ORDER, ARCHIVE_STATUS];

/** @deprecated используйте KANBAN_STATUS_ORDER */
export const STATUS_ORDER = KANBAN_STATUS_ORDER;

const LEGACY_STATUS_MAP = {
  in_progress: "in_work",
  closed: "approved",
};

export function formatAuthor(user) {
  if (!user) return "Пользователь";
  if (user.username) return `@${user.username}`;
  return user.first_name || "Пользователь";
}

export function formatMemberChip(user) {
  if (!user) return "";
  const name = user.username ? `@${escapeHtml(user.username)}` : escapeHtml(user.first_name);
  return `<span class="member-chip">${name}</span>`;
}

export function normalizeStatus(status) {
  const value = String(status || "new").toLowerCase();
  const mapped = LEGACY_STATUS_MAP[value] || value;
  if (mapped === ARCHIVE_STATUS) return ARCHIVE_STATUS;
  return KANBAN_STATUS_ORDER.includes(mapped) ? mapped : "new";
}

export function bindImagePicker(root, { existingUrl = null, onChange } = {}) {
  let selectedFile = null;
  let previewObjectUrl = null;
  let existingRemoved = false;

  const thumbWrap = root.querySelector(".rich-field-thumb");
  const preview = root.querySelector(".image-picker-preview");
  const addBtn = root.querySelector(".image-picker-add");
  const removeBtn = root.querySelector(".image-picker-remove");
  const fileInput = root.querySelector(".image-picker-input");

  const revokePreviewUrl = () => {
    if (previewObjectUrl) {
      URL.revokeObjectURL(previewObjectUrl);
      previewObjectUrl = null;
    }
  };

  const render = () => {
    const hasExisting = existingUrl && !existingRemoved && !selectedFile;
    const hasPreview = Boolean(selectedFile) || hasExisting;

    if (hasPreview) {
      thumbWrap.classList.remove("hidden");
      root.classList.add("has-image");
      addBtn.classList.add("hidden");
      removeBtn.classList.remove("hidden");

      if (selectedFile) {
        revokePreviewUrl();
        previewObjectUrl = URL.createObjectURL(selectedFile);
        preview.src = previewObjectUrl;
      } else {
        preview.src = existingUrl;
      }
    } else {
      thumbWrap.classList.add("hidden");
      preview.removeAttribute("src");
      root.classList.remove("has-image");
      addBtn.classList.remove("hidden");
      removeBtn.classList.add("hidden");
    }

    onChange?.();
  };

  addBtn.onclick = (event) => {
    event.stopPropagation();
    fileInput.click();
  };

  removeBtn.onclick = (event) => {
    event.stopPropagation();
    selectedFile = null;
    fileInput.value = "";
    if (existingUrl) existingRemoved = true;
    revokePreviewUrl();
    render();
  };

  fileInput.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    selectedFile = file;
    existingRemoved = false;
    render();
  });

  render();

  return {
    getFile: () => selectedFile,
    isExistingRemoved: () => existingRemoved,
    destroy: () => revokePreviewUrl(),
  };
}
