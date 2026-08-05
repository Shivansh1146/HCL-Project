/**
 * auth.js — Authentication Service Layer.
 *
 * Responsibilities:
 *  - Initiate GitHub OAuth redirect (preserving return URL)
 *  - Restore session from HttpOnly cookie via GET /auth/me
 *  - Perform logout via POST /auth/logout
 *  - Expose auth state helpers used by the router guard
 *
 * Security:
 *  - Tokens NEVER stored in localStorage or sessionStorage
 *  - Session lives exclusively in HttpOnly cookie (managed by backend)
 *  - Return URL validated before use to block open redirects
 */

import { api, ApiError } from "./api.js";
import { store }         from "../utils/state.js";
import { CONFIG }        from "../config/config.js";

// Allowed return URL hashes — must be a registered, protected route
const SAFE_RETURN_HASHES = new Set([
    CONFIG.ROUTES.DASHBOARD,
    CONFIG.ROUTES.REPOSITORIES,
    CONFIG.ROUTES.SETTINGS,
    CONFIG.ROUTES.PROFILE,
]);

/**
 * Sanitizes a return URL hash so we never redirect to an attacker-controlled destination.
 * @param {string|null} hash
 * @returns {string} A safe hash route
 */
function sanitizeReturnHash(hash) {
    if (hash && SAFE_RETURN_HASHES.has(hash)) return hash;
    return CONFIG.ROUTES.DASHBOARD;
}

class AuthService {
    /**
     * Attempt to restore an existing session from the HttpOnly cookie.
     * Called on every app bootstrap.
     *
     * @returns {Promise<boolean>} true if session was restored, false if not authenticated
     */
    async restoreSession() {
        try {
            const user = await api.getCurrentUser();
            store.setUser(user);
            return true;
        } catch (err) {
            // 401 = no valid session — expected for unauthenticated users
            if (err instanceof ApiError && err.isAuthError()) {
                store.reset();
                return false;
            }
            // Network error — don't wipe state, let router handle
            throw err;
        }
    }

    /**
     * Initiates the GitHub OAuth flow.
     * Saves the current route hash so we can restore it after callback.
     *
     * @param {string} [returnTo]  Hash route to return to after login (default: dashboard)
     */
    async initiateGitHubLogin(returnTo = CONFIG.ROUTES.DASHBOARD) {
        const safeReturn = sanitizeReturnHash(returnTo);

        // Persist the intended destination across the OAuth redirect
        // sessionStorage is safe here — this is NOT a token, just a UX hint
        try { sessionStorage.setItem("auth_return_to", safeReturn); } catch { /* private mode */ }

        // Ask backend for the GitHub authorization URL (contains CSRF state)
        const { authorization_url } = await api.getLoginUrl();

        // Full page redirect to GitHub — the only safe way to initiate OAuth
        window.location.href = authorization_url;
    }

    /**
     * Performs logout: clears server-side session cookie, then resets client state.
     */
    async logout() {
        try {
            await api.logout();
        } finally {
            // Always reset client state, even if the logout API call fails
            store.reset();
        }
    }

    /**
     * Reads and clears the saved return-to hash after OAuth callback.
     * @returns {string} A safe hash route
     */
    consumeReturnTo() {
        let hash = null;
        try {
            hash = sessionStorage.getItem("auth_return_to");
            sessionStorage.removeItem("auth_return_to");
        } catch { /* private mode */ }
        return sanitizeReturnHash(hash);
    }

    /** @returns {boolean} Whether the current store state reflects an authenticated user */
    isAuthenticated() {
        return store.getState().isAuthenticated;
    }
}

export const authService = new AuthService();
