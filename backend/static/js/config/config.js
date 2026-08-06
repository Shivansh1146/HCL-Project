/**
 * config.js — Centralized application configuration.
 *
 * All endpoints, route hashes, timeouts, and feature flags in one place.
 */
export const CONFIG = {
    APP_NAME: "AI Code Reviewer",
    DEBUG: window.location.hostname === "localhost",
    API_BASE_URL: "",  // Same origin — FastAPI serves frontend on same host

    AUTH_ENDPOINTS: {
        LOGIN:      "/auth/login",
        CALLBACK:   "/auth/callback",
        LOGOUT:     "/auth/logout",
        ME:         "/auth/me",
        AUDIT_LOGS: "/auth/audit-logs"
    },

    APP_ENDPOINTS: {
        INSTALLATIONS: "/api/app/installations",
        REPOS:         (instId) => `/api/app/installations/${instId}/repos`,
        SELECT_REPOS:  (instId) => `/api/app/installations/${instId}/repos/select`,
        SYNC_INSTALL:  (instId) => `/api/app/installations/${instId}/sync`,
        WEBHOOK_INSTALL: "/api/app/webhook",
        REPOS_LIST:    "/api/repositories",
        SYNC_REPOS:    "/api/repositories/sync",
    },

    PR_ENDPOINTS: {
        LIST:           "/api/prs",
        STATS:          "/api/prs/stats",
        DETAIL:         (owner, repo, prNum) => `/api/prs/${owner}/${repo}/${prNum}`,
        REVIEW:         (owner, repo, prNum) => `/api/prs/${owner}/${repo}/${prNum}/review`,
        PUBLISH_REVIEW: (owner, repo, prNum) => `/api/prs/${owner}/${repo}/${prNum}/publish-review`,
    },

    ANALYTICS_ENDPOINTS: {
        METRICS: "/api/analytics",
        EXPORT:  (format = "json") => `/api/analytics/export?format=${format}`
    },

    STATS_ENDPOINT: "/api/stats",

    ROUTES: {
        LOGIN:          "#/login",
        DASHBOARD:      "#/dashboard",
        REPOSITORIES:   "#/repositories",
        PULL_REQUESTS:  "#/pull-requests",
        REVIEW_HISTORY: "#/review-history",
        ANALYTICS:      "#/analytics",
        SETTINGS:       "#/settings",
        PROFILE:        "#/profile",
        UNAUTHORIZED:   "#/unauthorized",
        NOT_FOUND:      "#/404"
    },

    // Public routes that do NOT require auth
    PUBLIC_ROUTES: new Set(["#/login", "#/callback", "#/unauthorized", "#/404"])
};
