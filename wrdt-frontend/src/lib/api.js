/**
 * Single HTTP client for the WRDT API.
 *
 * Everything the UI knows about the backend goes through here. Three
 * things this centralises that were previously impossible, because the
 * app made no network calls at all and ran entirely on hardcoded arrays:
 *
 *  1. Token storage and the silent refresh. A meeting register is filled
 *     in over 20-30 minutes, which is longer than the access-token
 *     lifetime; without refresh the supervisor would be logged out
 *     mid-count and lose the sheet.
 *  2. A single in-flight refresh. Several panels load at once, so a
 *     naive implementation fires N refreshes in parallel, and because
 *     refresh tokens rotate, all but one are immediately invalidated and
 *     the user is kicked out. Concurrent 401s therefore await one shared
 *     promise.
 *  3. Uniform error shape. The API returns {error:{code,message}}; the
 *     UI needs a thrown Error carrying both so screens can show the
 *     server's own wording rather than "something went wrong".
 */

const BASE = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/$/, "");

const ACCESS_KEY = "wrdt.access";
const REFRESH_KEY = "wrdt.refresh";

export class ApiError extends Error {
  constructor(message, { status, code, details } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  set({ access_token, refresh_token }) {
    if (access_token) localStorage.setItem(ACCESS_KEY, access_token);
    if (refresh_token) localStorage.setItem(REFRESH_KEY, refresh_token);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

// Notifies the app shell when the session is gone for good, so it can
// drop back to the login screen from anywhere without prop drilling.
const listeners = new Set();
export function onUnauthorized(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
function broadcastLogout() {
  tokens.clear();
  listeners.forEach((fn) => fn());
}

let refreshInFlight = null;

async function doRefresh() {
  const refresh_token = tokens.refresh;
  if (!refresh_token) return false;
  try {
    const resp = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token }),
    });
    if (!resp.ok) return false;
    tokens.set(await resp.json());
    return true;
  } catch {
    return false;
  }
}

function refreshOnce() {
  if (!refreshInFlight) {
    refreshInFlight = doRefresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

async function parseError(resp) {
  let code = "http_error";
  let message = `Request failed (${resp.status})`;
  let details;
  try {
    const body = await resp.json();
    if (body?.error) {
      code = body.error.code || code;
      message = body.error.message || message;
      details = body.error.details;
    }
  } catch {
    /* non-JSON body: keep the generic message */
  }
  return new ApiError(message, { status: resp.status, code, details });
}

async function request(path, { method = "GET", body, raw = false, retry = true } = {}) {
  const headers = {};
  const access = tokens.access;
  if (access) headers.Authorization = `Bearer ${access}`;

  let payload;
  if (body instanceof FormData) {
    payload = body; // let the browser set the multipart boundary
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const resp = await fetch(`${BASE}${path}`, { method, headers, body: payload });

  if (resp.status === 401 && retry && tokens.refresh) {
    const ok = await refreshOnce();
    if (ok) return request(path, { method, body, raw, retry: false });
    broadcastLogout();
    throw new ApiError("Your session has expired. Please sign in again.", {
      status: 401,
      code: "session_expired",
    });
  }

  if (!resp.ok) throw await parseError(resp);
  if (resp.status === 204) return null;
  if (raw) return resp;
  return resp.json();
}

function qs(params = {}) {
  const usable = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null && v !== ""
  );
  if (!usable.length) return "";
  return "?" + new URLSearchParams(usable).toString();
}

export const api = {
  // -- auth ---------------------------------------------------------
  async login(email, password) {
    const resp = await fetch(`${BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!resp.ok) throw await parseError(resp);
    const data = await resp.json();
    tokens.set(data);
    return data;
  },
  async logout() {
    const refresh_token = tokens.refresh;
    try {
      // Fire-and-forget is wrong here: the point is to revoke the token
      // server-side, so wait for it before clearing local state.
      await request("/auth/logout", { method: "POST", body: { refresh_token }, retry: false });
    } catch {
      /* already invalid -- clearing locally is still correct */
    }
    tokens.clear();
  },
  me: () => request("/auth/me"),
  changePassword: (current_password, new_password) =>
    request("/auth/change-password", {
      method: "POST",
      body: { current_password, new_password },
    }),

  // -- regions ------------------------------------------------------
  listRegions: (p) => request(`/regions${qs(p)}`),
  createRegion: (name) => request("/regions", { method: "POST", body: { name } }),
  updateRegion: (id, body) => request(`/regions/${id}`, { method: "PUT", body }),
  deleteRegion: (id) => request(`/regions/${id}`, { method: "DELETE" }),

  // -- groups -------------------------------------------------------
  listGroups: (p) => request(`/groups${qs(p)}`),
  listGroupsInRegion: (regionId, p) => request(`/regions/${regionId}/groups${qs(p)}`),
  getGroup: (id) => request(`/groups/${id}`),
  createGroup: (regionId, body) =>
    request(`/regions/${regionId}/groups`, { method: "POST", body }),
  updateGroup: (id, body) => request(`/groups/${id}`, { method: "PUT", body }),
  deleteGroup: (id) => request(`/groups/${id}`, { method: "DELETE" }),

  // -- members ------------------------------------------------------
  listMembers: (p) => request(`/members${qs(p)}`),
  listMembersInGroup: (groupId, p) => request(`/groups/${groupId}/members${qs(p)}`),
  getMember: (id) => request(`/members/${id}`),
  createMember: (groupId, body) =>
    request(`/groups/${groupId}/members`, { method: "POST", body }),
  updateMember: (id, body) => request(`/members/${id}`, { method: "PUT", body }),
  deleteMember: (id) => request(`/members/${id}`, { method: "DELETE" }),

  // -- meetings -----------------------------------------------------
  listMeetings: (groupId, p) => request(`/groups/${groupId}/meetings${qs(p)}`),
  startMeeting: (groupId) => request(`/groups/${groupId}/meetings/start`, { method: "POST" }),
  getMeeting: (id) => request(`/meetings/${id}`),
  saveEntry: (meetingId, memberId, body) =>
    request(`/meetings/${meetingId}/entries/${memberId}`, { method: "PUT", body }),
  saveEntriesBulk: (meetingId, entries) =>
    request(`/meetings/${meetingId}/entries`, { method: "PUT", body: { entries } }),
  overrideLoan: (meetingId, memberId, loan_remaining) =>
    request(`/meetings/${meetingId}/entries/${memberId}/loan-override`, {
      method: "PATCH",
      body: { loan_remaining },
    }),
  resetLoanOverride: (meetingId, memberId) =>
    request(`/meetings/${meetingId}/entries/${memberId}/loan-override`, { method: "DELETE" }),
  addExpense: (meetingId, body) =>
    request(`/meetings/${meetingId}/expenses`, { method: "POST", body }),
  deleteExpense: (meetingId, expenseId) =>
    request(`/meetings/${meetingId}/expenses/${expenseId}`, { method: "DELETE" }),
  completeMeeting: (meetingId) =>
    request(`/meetings/${meetingId}/complete`, { method: "POST" }),
  exportMeetingUrl: (meetingId) => `${BASE}/meetings/${meetingId}/export.xlsx`,

  // -- reports ------------------------------------------------------
  dashboard: () => request("/reports/dashboard"),
  collections: (days = 60) => request(`/reports/collections${qs({ days })}`),
  loanLedger: (p) => request(`/reports/loans${qs(p)}`),
  expenseReport: (p) => request(`/reports/expenses${qs(p)}`),
  groupReport: (id, p) => request(`/reports/groups/${id}${qs(p)}`),
  regionReport: (id, p) => request(`/reports/regions/${id}${qs(p)}`),
  monthlyReport: (year, month) => request(`/reports/monthly${qs({ year, month })}`),
  memberLedger: (id) => request(`/reports/members/${id}/ledger`),
  activity: (p) => request(`/reports/activity${qs(p)}`),

  // -- users --------------------------------------------------------
  listUsers: (p) => request(`/users${qs(p)}`),
  listRoles: () => request("/users/roles"),
  createUser: (body) => request("/users", { method: "POST", body }),
  updateUser: (id, body) => request(`/users/${id}`, { method: "PUT", body }),
  deactivateUser: (id) => request(`/users/${id}`, { method: "DELETE" }),
  listAssignments: (userId) => request(`/users/${userId}/group-assignments`),
  assignGroup: (user_id, group_id) =>
    request("/users/group-assignments", { method: "POST", body: { user_id, group_id } }),
  unassignGroup: (userId, groupId) =>
    request(`/users/${userId}/group-assignments/${groupId}`, { method: "DELETE" }),

  // -- import -------------------------------------------------------
  importPreview: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request("/import/preview", { method: "POST", body: fd });
  },
  importCommit: (batchId) => request(`/import/${batchId}/commit`, { method: "POST" }),
  importTemplateUrl: () => `${BASE}/import/template.xlsx`,

  // Downloads need the bearer token, so they cannot be a plain <a href>.
  async download(url, filename) {
    const resp = await request(url.replace(BASE, ""), { raw: true });
    const blob = await resp.blob();
    const href = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = href;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(href);
  },
};
