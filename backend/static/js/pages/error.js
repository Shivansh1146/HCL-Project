/**
 * pages/error.js — Friendly Enterprise Error Pages (401, 403, 404, 500).
 *
 * Provides accessible, user-friendly error views with action buttons (Retry, Return to Dashboard, Login).
 */

import { dom } from "../utils/dom.js";
import { CONFIG } from "../config/config.js";

const ERROR_DETAILS = {
    401: {
        title: "401 — Session Expired",
        description: "Your authentication session has expired or is invalid. Please sign in again to access the enterprise dashboard.",
        badge: "Authentication Required",
        badgeClass: "badge-warning",
        primaryActionText: "Sign In with GitHub",
        primaryActionHash: CONFIG.ROUTES.LOGIN
    },
    403: {
        title: "403 — Access Forbidden",
        description: "You do not have permission to view this resource or organization. Contact your system administrator if you believe this is an error.",
        badge: "Permission Denied",
        badgeClass: "badge-error",
        primaryActionText: "Return to Dashboard",
        primaryActionHash: CONFIG.ROUTES.DASHBOARD
    },
    404: {
        title: "404 — Page Not Found",
        description: "The requested route or resource could not be found on this server. Check the URL or navigate back to safety.",
        badge: "Not Found",
        badgeClass: "badge-info",
        primaryActionText: "Return to Dashboard",
        primaryActionHash: CONFIG.ROUTES.DASHBOARD
    },
    500: {
        title: "500 — Server Internal Error",
        description: "An unexpected error occurred while processing your request on the backend. Our telemetry system has logged this incident.",
        badge: "Internal Server Error",
        badgeClass: "badge-error",
        primaryActionText: "Try Again",
        primaryActionHash: CONFIG.ROUTES.DASHBOARD
    }
};

/**
 * Renders an error page into the outlet.
 * @param {HTMLElement} outlet
 * @param {number|string} code Error HTTP status code (401, 403, 404, 500)
 * @param {string} [customMessage] Optional override message
 */
export function renderErrorPage(outlet, code = 404, customMessage = null) {
    const errorInfo = ERROR_DETAILS[code] || ERROR_DETAILS[404];

    outlet.innerHTML = "";

    const wrapper = document.createElement("div");
    wrapper.className = "animate-fade-up";
    wrapper.style.cssText = "display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:65vh;text-align:center;padding:2rem 1rem;";

    const card = document.createElement("div");
    card.className = "glass-card";
    card.style.cssText = "max-width:520px;width:100%;padding:2.5rem 2rem;display:flex;flex-direction:column;align-items:center;";

    const safeTitle = dom.escape(errorInfo.title);
    const safeDesc = dom.escape(customMessage || errorInfo.description);

    card.innerHTML = `
        <div style="width:60px;height:60px;border-radius:50%;background:rgba(239,68,68,0.12);color:var(--color-error);display:flex;align-items:center;justify-content:center;margin-bottom:1.25rem;">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        </div>
        <span class="badge ${errorInfo.badgeClass}" style="margin-bottom:0.75rem;">${errorInfo.badge}</span>
        <h1 style="font-size:1.5rem;font-weight:800;letter-spacing:-0.02em;margin-bottom:0.5rem;">${safeTitle}</h1>
        <p style="color:var(--text-secondary);font-size:0.9rem;line-height:1.6;margin-bottom:2rem;">${safeDesc}</p>
        <div style="display:flex;gap:0.75rem;flex-wrap:wrap;justify-content:center;">
            <a href="${errorInfo.primaryActionHash}" class="btn btn-primary" style="text-decoration:none;">
                ${errorInfo.primaryActionText}
            </a>
            <button type="button" id="error-back-btn" class="btn btn-secondary">Go Back</button>
        </div>
    `;

    card.querySelector("#error-back-btn")?.addEventListener("click", () => window.history.back());

    wrapper.appendChild(card);
    outlet.appendChild(wrapper);
}
