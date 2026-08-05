/**
 * toast.js — XSS-safe Toast Notification Component.
 *
 * Fixes from v1:
 *  - Messages are now set via textContent (NOT innerHTML) — XSS safe
 *  - Single container, never duplicated
 *  - toastOut animation defined in CSS via class
 *  - aria-live="assertive" for errors, "polite" for others
 */

const ICONS = {
    success: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>`,
    error:   `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.5" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
    warning: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2.5" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
    info:    `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2.5" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`
};

class ToastManager {
    constructor() {
        /** @type {HTMLElement|null} */
        this._container = null;
    }

    _getContainer() {
        if (!this._container || !document.body.contains(this._container)) {
            let el = document.getElementById("toast-container");
            if (!el) {
                el = document.createElement("div");
                el.id = "toast-container";
                document.body.appendChild(el);
            }
            el.setAttribute("aria-live", "polite");
            el.setAttribute("aria-label", "Notifications");
            this._container = el;
        }
        return this._container;
    }

    _show(message, type = "info", duration = 4500) {
        const container = this._getContainer();

        // Build toast using DOM API — NOT innerHTML for message (XSS safe)
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        toast.setAttribute("role", type === "error" ? "alert" : "status");

        // Icon (SVG is static, not user-supplied — safe to use innerHTML here)
        const iconEl = document.createElement("span");
        iconEl.innerHTML = ICONS[type];
        toast.appendChild(iconEl);

        // Message — SAFE: textContent, not innerHTML
        const msgEl = document.createElement("span");
        msgEl.style.cssText = "flex:1;font-size:0.9rem;font-weight:500;";
        msgEl.textContent = message;   // ← XSS-safe: user data never goes to innerHTML
        toast.appendChild(msgEl);

        // Dismiss button
        const closeBtn = document.createElement("button");
        closeBtn.type = "button";
        closeBtn.setAttribute("aria-label", "Dismiss notification");
        closeBtn.style.cssText = "background:none;border:none;color:#64748b;cursor:pointer;padding:0;line-height:1;display:flex;";
        closeBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
        closeBtn.addEventListener("click", () => this._dismiss(toast));
        toast.appendChild(closeBtn);

        container.appendChild(toast);

        if (duration > 0) {
            setTimeout(() => this._dismiss(toast), duration);
        }

        return toast;
    }

    _dismiss(toast) {
        if (!toast.parentElement) return;
        toast.classList.add("toast-out");
        setTimeout(() => toast.remove(), 280);
    }

    success(message, duration) { return this._show(message, "success", duration); }
    error(message, duration)   { return this._show(message, "error",   duration); }
    warning(message, duration) { return this._show(message, "warning", duration); }
    info(message, duration)    { return this._show(message, "info",    duration); }
}

export const Toast = new ToastManager();
