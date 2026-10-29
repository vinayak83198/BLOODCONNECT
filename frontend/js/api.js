/**
 * api.js — thin fetch wrapper around the FastAPI backend.
 * Handles JWT storage, JSON encoding/decoding, and normalized errors
 * so every page's script can just `await` a call and catch one shape
 * of error.
 */
const API_BASE_URL = window.BLOODCONNECT_API_BASE_URL ||
  (["localhost", "127.0.0.1"].includes(window.location.hostname)
    ? "http://127.0.0.1:8000"
    : "https://bloodconnect-kfks.onrender.com");
const TOKEN_KEY = "bloodconnect_token";
const USER_KEY = "bloodconnect_user";

class ApiError extends Error {
  constructor(message, status, fields) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fields = fields || [];

  }
}

const auth = {
  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  },
  getUser() {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  },
  setSession(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
  isLoggedIn() {
    return Boolean(this.getToken());
  },
  /** Call at the top of any page that requires a logged-in user. */
  requireSession() {
    if (!this.isLoggedIn()) {
      window.location.href = "index.html";
    }
  },
};

async function apiRequest(path, { method = "GET", body, auth: needsAuth = true, params } = {}) {
  let url = `${API_BASE_URL}${path}`;
  if (params) {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
    );
    url += `?${query.toString()}`;
  }

  const headers = { "Content-Type": "application/json" };
  if (needsAuth) {
    const token = auth.getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (networkErr) {
    throw new ApiError(
      "Can't reach the BloodConnect server. Check it's running and try again.",
      0
    );
  }

  let payload = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    if (response.status === 401 && needsAuth) {
      auth.clearSession();
      window.location.href = "index.html";
    }
    // FastAPI normally returns {"detail": "..."}; some endpoints may
    // return {"error": {"message": "...", "fields": [...]}}.
    const errInfo = payload && payload.error ? payload.error : {};
    let message = errInfo.message || (payload && typeof payload.detail === "string" ? payload.detail : "");
    let fields = errInfo.fields || [];
    if (!message && payload && Array.isArray(payload.detail)) {
      message = payload.detail.map((item) => {
        const field = Array.isArray(item.loc) ? item.loc.filter((part) => part !== "body").join(" → ") : "Input";
        return `${field}: ${item.msg || "Invalid value"}`;
      }).join("; ");
      fields = payload.detail;
    }
    throw new ApiError(
      message || `Request failed (${response.status}). Please check the information and try again.`,
      response.status,
      fields
    );
  }

  return payload;
}

const api = {
adminAccess: () => apiRequest("/api/admin/access"),
  signup: (data) => apiRequest("/api/auth/signup", { method: "POST", body: data, auth: false }),
  login: (data) => apiRequest("/api/auth/login", { method: "POST", body: data, auth: false }),
  verifyLoginOtp: (email, otp) => apiRequest("/api/auth/verify-login-otp", { method: "POST", body: { email, otp }, auth: false }),
  verifyEmail: (token) => apiRequest("/api/auth/verify-email", { method: "POST", body: { token }, auth: false }),
  resendVerification: (email) => apiRequest("/api/auth/resend-verification", { method: "POST", body: { email }, auth: false }),
  forgotPassword: (email) => apiRequest("/api/auth/forgot-password", { method: "POST", body: { email }, auth: false }),
  resetPassword: (token, new_password) => apiRequest("/api/auth/reset-password", { method: "POST", body: { token, new_password }, auth: false }),
  me: () => apiRequest("/api/auth/me"),
  createTelegramLink: () => apiRequest("/api/telegram/link", { method: "POST" }),
  telegramStatus: () => apiRequest("/api/telegram/status"),

  updateProfile: (data) => apiRequest("/api/donors/me", { method: "PUT", body: data }),
  searchDonors: (params) => apiRequest("/api/donors/search", { params }),

  createRequest: (data) => apiRequest("/api/requests", { method: "POST", body: data }),
  myRequests: () => apiRequest("/api/requests/mine"),
  incomingRequests: () => apiRequest("/api/requests/incoming"),
  acceptRequest: (requestId) => apiRequest(`/api/requests/${requestId}/accept`, { method: "POST" }),
  fulfillRequest: (requestId) => apiRequest(`/api/requests/${requestId}/fulfill`, { method: "POST" }),
};

window.BloodConnect = { api, auth, ApiError };
