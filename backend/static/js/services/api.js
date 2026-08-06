/**
 * api.js — Production-grade Centralized API Service Layer.
 *
 * Features:
 *  - AbortController per-request with configurable timeout
 *  - Exponential backoff retry (jitter included)
 *  - Global request/response interceptors
 *  - Structured ApiError with status, code, data
 *  - Session expiry redirect
 *  - File upload support (multipart bypass)
 *  - Logging hooks (interceptors)
 *  - No duplicate fetch() calls elsewhere in the codebase
 */

import { CONFIG } from "../config/config.js";
import { store } from "../utils/state.js";

// ---------------------------------------------------------------------------
// Structured Error Type
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  /**
   * @param {string} message  Human-readable description
   * @param {number} status   HTTP status code (0 = network failure)
   * @param {string} code     Machine-readable error code
   * @param {*}      data     Raw response body
   */
  constructor(message, status = 0, code = "UNKNOWN_ERROR", data = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.data = data;
    this.timestamp = new Date().toISOString();
  }

  isAuthError() {
    return this.status === 401;
  }
  isForbidden() {
    return this.status === 403;
  }
  isNotFound() {
    return this.status === 404;
  }
  isServerError() {
    return this.status >= 500;
  }
  isNetworkError() {
    return this.status === 0;
  }
}

// ---------------------------------------------------------------------------
// Interceptor Registry
// ---------------------------------------------------------------------------

class InterceptorRegistry {
  constructor() {
    this._request = [];
    this._response = [];
    this._error = [];
  }

  addRequest(fn) {
    this._request.push(fn);
    return () => (this._request = this._request.filter((f) => f !== fn));
  }
  addResponse(fn) {
    this._response.push(fn);
    return () => (this._response = this._response.filter((f) => f !== fn));
  }
  addError(fn) {
    this._error.push(fn);
    return () => (this._error = this._error.filter((f) => f !== fn));
  }

  async runRequest(config) {
    let c = config;
    for (const fn of this._request) c = (await fn(c)) || c;
    return c;
  }
  async runResponse(res) {
    let r = res;
    for (const fn of this._response) r = (await fn(r)) || r;
    return r;
  }
  async runError(err) {
    for (const fn of this._error) await fn(err);
  }
}

// ---------------------------------------------------------------------------
// Main API Service
// ---------------------------------------------------------------------------

class ApiService {
  constructor() {
    this._maxRetries = 3;
    this._baseDelay = 600; // ms — doubles each attempt (exponential backoff)
    this._timeout = 15000; // ms — 15 second request timeout
    this.interceptors = new InterceptorRegistry();

    // Default logging interceptor
    this.interceptors.addRequest((config) => {
      if (CONFIG.DEBUG)
        console.debug(`[API] ➜ ${config.method || "GET"} ${config.url}`);
      return config;
    });
    this.interceptors.addResponse((res) => {
      if (CONFIG.DEBUG) console.debug(`[API] ✓ ${res._status} ${res._url}`);
      return res;
    });
    this.interceptors.addError((err) => {
      if (CONFIG.DEBUG) console.warn(`[API] ✗ ${err.status} ${err.message}`);
    });
  }

  /**
   * Core request with timeout, retry, interceptors, and error normalization.
   *
   * @param {string} endpoint   Path (appended to API_BASE_URL)
   * @param {object} options    fetch() options override
   * @param {number} attempt    Internal retry counter — do not pass manually
   */
  async request(endpoint, options = {}, attempt = 0) {
    const url = `${CONFIG.API_BASE_URL}${endpoint}`;
    const isFileUpload = options.body instanceof FormData;

    // Build config — interceptors may modify it
    let config = await this.interceptors.runRequest({
      url,
      method: options.method || "GET",
      credentials: "include",
      headers: isFileUpload
        ? { ...options.headers } // Let browser set Content-Type for FormData
        : { "Content-Type": "application/json", ...options.headers },
      ...options,
    });

    // Per-request AbortController for timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this._timeout);
    config.signal = controller.signal;

    let response;
    try {
      response = await fetch(config.url, config);
      clearTimeout(timeoutId);
    } catch (err) {
      clearTimeout(timeoutId);
      if (err.name === "AbortError") {
        throw new ApiError(
          `Request timed out after ${this._timeout}ms`,
          0,
          "TIMEOUT"
        );
      }
      // Retry on network failure with exponential backoff + jitter
      if (attempt < this._maxRetries) {
        await this._backoff(attempt);
        return this.request(endpoint, options, attempt + 1);
      }
      const netErr = new ApiError(
        "Network error. Please check your connection.",
        0,
        "NETWORK_ERROR"
      );
      await this.interceptors.runError(netErr);
      throw netErr;
    }

    // Retry on 429 (rate limit) or 5xx (server error)
    if (
      (response.status === 429 || response.status >= 500) &&
      attempt < this._maxRetries
    ) {
      const retryAfter =
        parseInt(response.headers.get("Retry-After") || "0") * 1000;
      await this._backoff(attempt, retryAfter);
      return this.request(endpoint, options, attempt + 1);
    }

    // Session expired — clear auth state and redirect
    if (response.status === 401) {
      store.reset();
      window.location.hash = CONFIG.ROUTES.LOGIN;
      const authErr = new ApiError(
        "Session expired. Please log in again.",
        401,
        "UNAUTHORIZED"
      );
      await this.interceptors.runError(authErr);
      throw authErr;
    }

    // Parse response body
    const contentType = response.headers.get("Content-Type") || "";
    let data;
    try {
      data = contentType.includes("application/json")
        ? await response.json()
        : await response.text();
    } catch {
      data = null;
    }

    if (!response.ok) {
      const message =
        typeof data === "object" && data
          ? data.detail || data.message || `HTTP ${response.status}`
          : `HTTP ${response.status}`;
      const code =
        typeof data === "object" && data?.code
          ? data.code
          : `HTTP_${response.status}`;
      const apiErr = new ApiError(message, response.status, code, data);
      await this.interceptors.runError(apiErr);
      throw apiErr;
    }

    // Response interceptors use request metadata for debug logging. Only
    // objects can safely carry that metadata; a successful endpoint may
    // legitimately return an empty body or a text response.
    if (data && typeof data === "object") {
      data._status = response.status;
      data._url = url;
      const finalData = await this.interceptors.runResponse(data);
      delete finalData?._status;
      delete finalData?._url;
      return finalData;
    }

    return data;
  }

  /**
   * Exponential backoff with jitter.
   * Delay = min(baseDelay * 2^attempt, 10000) + random(0..200)ms
   */
  _backoff(attempt, minDelay = 0) {
    const delay = Math.max(
      minDelay,
      Math.min(this._baseDelay * Math.pow(2, attempt), 10000) +
        Math.random() * 200
    );
    return new Promise((r) => setTimeout(r, delay));
  }

  // ---------------------------------------------------------------------------
  // Auth Endpoints
  // ---------------------------------------------------------------------------

  getLoginUrl() {
    return this.request(CONFIG.AUTH_ENDPOINTS.LOGIN);
  }
  getCurrentUser() {
    return this.request(CONFIG.AUTH_ENDPOINTS.ME);
  }
  logout() {
    return this.request(CONFIG.AUTH_ENDPOINTS.LOGOUT, { method: "POST" });
  }

  // ---------------------------------------------------------------------------
  // GitHub App Endpoints
  // ---------------------------------------------------------------------------

  getAppStatus() {
    return this.request("/api/app/status");
  }

  getInstallUrl() {
    return this.request("/api/app/install");
  }

  getInstallations() {
    return this.request(CONFIG.APP_ENDPOINTS.INSTALLATIONS);
  }

  getReposForInstallation(installationId) {
    return this.request(CONFIG.APP_ENDPOINTS.REPOS(installationId));
  }

  selectRepos(installationId, repoFullNames) {
    return this.request(CONFIG.APP_ENDPOINTS.SELECT_REPOS(installationId), {
      method: "POST",
      body: JSON.stringify({ repo_full_names: repoFullNames }),
    });
  }

  syncInstallation(installationId) {
    return this.request(CONFIG.APP_ENDPOINTS.SYNC_INSTALL(installationId), {
      method: "POST",
    });
  }

  /** Fetch all synced repositories from the DB for the current user. */
  getRepositories() {
    return this.request(CONFIG.APP_ENDPOINTS.REPOS_LIST);
  }

  /**
   * Trigger a full resync from GitHub (installation token → GET /installation/repositories).
   * Returns { status, synced_count, repositories }.
   */
  syncRepositories() {
    return this.request(CONFIG.APP_ENDPOINTS.SYNC_REPOS, { method: "POST" });
  }

  // ---------------------------------------------------------------------------
  // Pull Request Endpoints
  // ---------------------------------------------------------------------------

  getPullRequests(params = {}) {
    const query = new URLSearchParams();
    if (params.page) query.append("page", params.page);
    if (params.per_page) query.append("per_page", params.per_page);
    if (params.state) query.append("state", params.state);
    if (params.repo) query.append("repo", params.repo);

    const url = query.toString()
      ? `${CONFIG.PR_ENDPOINTS.LIST}?${query}`
      : CONFIG.PR_ENDPOINTS.LIST;
    return this.request(url);
  }

  getPullRequestStats() {
    return this.request("/api/prs/stats");
  }

  getPullRequestByNumber(number, repo = null) {
    const query = repo ? `?repo=${encodeURIComponent(repo)}` : "";
    return this.request(`/api/prs/${number}${query}`);
  }

  getPullRequestDetail(owner, repo, prNumber) {
    return this.request(CONFIG.PR_ENDPOINTS.DETAIL(owner, repo, prNumber));
  }

  triggerPullRequestReview(owner, repo, prNumber) {
    return this.request(CONFIG.PR_ENDPOINTS.REVIEW(owner, repo, prNumber), {
      method: "POST",
    });
  }

  publishPullRequestReview(owner, repo, prNumber) {
    return this.request(CONFIG.PR_ENDPOINTS.PUBLISH_REVIEW(owner, repo, prNumber), {
      method: "POST",
    });
  }

  // ---------------------------------------------------------------------------
  // Analytics Endpoints
  // ---------------------------------------------------------------------------

  getAnalytics(params = {}) {
    const query = new URLSearchParams();
    if (params.repo) query.append("repo", params.repo);
    if (params.date_range) query.append("date_range", params.date_range);

    const url = query.toString()
      ? `${CONFIG.ANALYTICS_ENDPOINTS.METRICS}?${query}`
      : CONFIG.ANALYTICS_ENDPOINTS.METRICS;
    return this.request(url);
  }

  exportAnalytics(format = "json") {
    window.open(CONFIG.ANALYTICS_ENDPOINTS.EXPORT(format), "_blank");
  }

  getAuditLogs(limit = 50) {
    return this.request(`${CONFIG.AUTH_ENDPOINTS.AUDIT_LOGS}?limit=${limit}`);
  }

  // ---------------------------------------------------------------------------
  // Stats Endpoint
  // ---------------------------------------------------------------------------

  getStats() {
    return this.request(CONFIG.STATS_ENDPOINT);
  }
}

export const api = new ApiService();
