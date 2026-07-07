import { getInitData, isDevMode } from "/js/telegram.js?v=16";

const API_BASE = "/api";

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function headers(json = true) {
  const h = {};
  if (json) h["Content-Type"] = "application/json";
  const initData = getInitData();
  if (initData) {
    h["X-Telegram-Init-Data"] = initData;
  } else if (isDevMode()) {
    h["X-Dev-User-Id"] = "123456789";
  }
  return h;
}

async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...headers(!isFormData), ...options.headers },
  });

  if (res.status === 204) return null;

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    let message = Array.isArray(detail)
      ? detail.map((item) => item.msg || item).join(", ")
      : detail;
    if (!message || message === "Internal Server Error") {
      const defaults = {
        400: "Некорректный запрос",
        401: "Требуется авторизация через Telegram",
        403: "Недостаточно прав",
        404: "Не найдено",
        422: "Проверьте введённые данные",
        429: "Слишком много запросов, подождите",
        500: "Ошибка сервера. Попробуйте позже",
      };
      message = defaults[res.status] || `Ошибка запроса (HTTP ${res.status})`;
    }
    throw new ApiError(message, res.status);
  }
  return data;
}

function buildTaskForm(payload, { image = null, removeImage = false } = {}) {
  const form = new FormData();
  form.append("title", payload.title);
  form.append("status", payload.status);
  form.append("description", payload.description ?? "");
  form.append("deadline", payload.deadline ?? "");
  if (removeImage) form.append("remove_description_image", "true");
  if (image) form.append("description_image", image);
  return form;
}

export const api = {
  listBoards: () => request("/boards"),
  createBoard: (title) => request("/boards", { method: "POST", body: JSON.stringify({ title }) }),
  getBoard: (id) => request(`/boards/${id}`),
  updateBoard: (id, title) =>
    request(`/boards/${id}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  deleteBoard: (id) => request(`/boards/${id}`, { method: "DELETE" }),
  listMembers: (boardId) => request(`/boards/${boardId}/members`),
  addMember: (boardId, payload) =>
    request(`/boards/${boardId}/members`, { method: "POST", body: JSON.stringify(payload) }),
  removeMember: (boardId, memberId) =>
    request(`/boards/${boardId}/members/${memberId}`, { method: "DELETE" }),
  createTask: (boardId, payload, options = {}) =>
    request(`/boards/${boardId}/tasks`, {
      method: "POST",
      body: buildTaskForm(payload, options),
    }),
  updateTask: (taskId, payload, options = {}) =>
    request(`/tasks/${taskId}`, {
      method: "PATCH",
      body: buildTaskForm(payload, options),
    }),
  deleteTask: (taskId) => request(`/tasks/${taskId}`, { method: "DELETE" }),
  listComments: (taskId) => request(`/tasks/${taskId}/comments`),
  addComment: (taskId, { text = "", image = null }) => {
    const form = new FormData();
    form.append("text", text);
    if (image) form.append("image", image);
    return request(`/tasks/${taskId}/comments`, { method: "POST", body: form });
  },
  updateComment: (taskId, commentId, { text = "", image = null, removeImage = false } = {}) => {
    const form = new FormData();
    form.append("text", text);
    if (removeImage) form.append("remove_image", "true");
    if (image) form.append("image", image);
    return request(`/tasks/${taskId}/comments/${commentId}`, { method: "PATCH", body: form });
  },
  deleteComment: (taskId, commentId) =>
    request(`/tasks/${taskId}/comments/${commentId}`, { method: "DELETE" }),
};
