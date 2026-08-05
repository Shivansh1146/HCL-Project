/**
 * modal.js — Accessible, XSS-safe Modal Component.
 *
 * Fixes from v1:
 *  - title and body rendered via textContent/DOM API, not innerHTML (XSS safe)
 *  - Exception: callers may pass pre-sanitized HTML via `bodyHTML` only for static content
 *  - Focus trap: Tab/Shift+Tab cycle within modal, Escape to close
 *  - Removes scroll when open (prevents background scrolling)
 *  - aria-modal, aria-labelledby, role="dialog" for screen readers
 */

export class Modal {
    /**
     * @param {object} opts
     * @param {string}   opts.title           Modal heading (treated as plain text)
     * @param {string}   [opts.body]          Body text (treated as plain text — safe)
     * @param {string}   [opts.bodyHTML]      Pre-sanitized static HTML body (use only for static strings)
     * @param {string}   [opts.confirmText]
     * @param {string}   [opts.cancelText]
     * @param {Function} [opts.onConfirm]
     * @param {Function} [opts.onCancel]
     * @param {boolean}  [opts.danger]        Use red confirm button
     */
    constructor({ title = "", body = "", bodyHTML = null, confirmText = "Confirm", cancelText = "Cancel", onConfirm = null, onCancel = null, danger = false } = {}) {
        this._onConfirm = onConfirm;
        this._onCancel  = onCancel;
        this._el        = this._build({ title, body, bodyHTML, confirmText, cancelText, danger });
        document.body.appendChild(this._el);
    }

    _build({ title, body, bodyHTML, confirmText, cancelText, danger }) {
        // Overlay
        const overlay = document.createElement("div");
        overlay.className = "modal-overlay";
        overlay.setAttribute("role", "dialog");
        overlay.setAttribute("aria-modal", "true");
        overlay.setAttribute("aria-labelledby", "modal-title-" + Date.now());

        // Box
        const box = document.createElement("div");
        box.className = "modal-box";

        // Header
        const header = document.createElement("div");
        header.style.cssText = "display:flex;justify-content:space-between;align-items:center;margin-bottom:1.25rem;";

        const titleEl = document.createElement("h2");
        titleEl.id    = overlay.getAttribute("aria-labelledby");
        titleEl.style.cssText = "font-size:1.15rem;font-weight:700;";
        titleEl.textContent = title;   // XSS safe: textContent

        const closeBtn = document.createElement("button");
        closeBtn.type      = "button";
        closeBtn.className = "btn btn-ghost";
        closeBtn.setAttribute("aria-label", "Close dialog");
        closeBtn.style.cssText = "padding:0.35rem;";
        closeBtn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
        closeBtn.addEventListener("click", () => this.close());

        header.append(titleEl, closeBtn);

        // Body
        const bodyEl = document.createElement("div");
        bodyEl.style.cssText = "color:var(--text-secondary);font-size:0.95rem;line-height:1.7;margin-bottom:1.75rem;";
        if (bodyHTML) {
            bodyEl.innerHTML = bodyHTML;  // Caller's responsibility to sanitize
        } else {
            bodyEl.textContent = body;   // XSS safe: textContent
        }

        // Footer actions
        const actions = document.createElement("div");
        actions.style.cssText = "display:flex;gap:0.75rem;justify-content:flex-end;";

        const cancelBtn = document.createElement("button");
        cancelBtn.type      = "button";
        cancelBtn.className = "btn btn-secondary";
        cancelBtn.textContent = cancelText;
        cancelBtn.addEventListener("click", () => { if (this._onCancel) this._onCancel(); this.close(); });

        const confirmBtn = document.createElement("button");
        confirmBtn.type       = "button";
        confirmBtn.className  = `btn ${danger ? "btn-danger" : "btn-primary"}`;
        confirmBtn.textContent = confirmText;
        confirmBtn.addEventListener("click", () => { if (this._onConfirm) this._onConfirm(); this.close(); });

        actions.append(cancelBtn, confirmBtn);
        box.append(header, bodyEl, actions);
        overlay.appendChild(box);

        // Close on backdrop click
        overlay.addEventListener("click", e => { if (e.target === overlay) this.close(); });

        // Keyboard: Escape to close, Tab trap
        overlay.addEventListener("keydown", e => {
            if (e.key === "Escape") { this.close(); return; }
            if (e.key === "Tab")    this._trapTab(e, overlay);
        });

        this._confirmBtn = confirmBtn;
        this._cancelBtn  = cancelBtn;
        return overlay;
    }

    _trapTab(e, container) {
        const focusable = Array.from(container.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )).filter(el => !el.disabled);

        if (!focusable.length) { e.preventDefault(); return; }

        const first = focusable[0];
        const last  = focusable[focusable.length - 1];

        if (e.shiftKey) {
            if (document.activeElement === first) { e.preventDefault(); last.focus(); }
        } else {
            if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
        }
    }

    open() {
        requestAnimationFrame(() => this._el.classList.add("active"));
        document.body.style.overflow = "hidden";  // Prevent background scroll
        this._confirmBtn.focus();
        return this;
    }

    close() {
        this._el.classList.remove("active");
        document.body.style.overflow = "";
        setTimeout(() => { if (this._el.parentElement) this._el.remove(); }, 300);
    }

    /**
     * Static convenience factory for confirmation dialogs.
     */
    static confirm({ title, body, onConfirm, danger = false, confirmText }) {
        const modal = new Modal({
            title, body, onConfirm, danger,
            confirmText: confirmText ?? (danger ? "Delete" : "Confirm"),
        });
        return modal.open();
    }
}
