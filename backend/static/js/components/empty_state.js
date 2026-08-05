/**
 * empty_state.js — Empty State Display Component.
 *
 * Usage:
 *   import { EmptyState } from "../components/empty_state.js";
 *   EmptyState.render(containerEl, {...});
 *
 * OR (backward compatibility)
 *
 *   import { renderEmptyState } from "../components/empty_state.js";
 *   renderEmptyState(containerEl, {...});
 */

export const EmptyState = {
  ICONS: {
    repos: `<svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="40" cy="40" r="40" fill="rgba(59,130,246,0.07)"/><rect x="24" y="22" width="32" height="36" rx="4" stroke="#3b82f6" stroke-width="2"/><path d="M30 32h20M30 38h14M30 44h10" stroke="#3b82f6" stroke-width="2" stroke-linecap="round"/></svg>`,

    orgs: `<svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="40" cy="40" r="40" fill="rgba(168,85,247,0.07)"/><circle cx="40" cy="32" r="10" stroke="#a855f7" stroke-width="2"/><path d="M20 62c0-11.046 8.954-20 20-20s20 8.954 20 20" stroke="#a855f7" stroke-width="2"/></svg>`,

    auth: `<svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="40" cy="40" r="40" fill="rgba(245,158,11,0.07)"/><rect x="26" y="36" width="28" height="22" rx="4" stroke="#f59e0b" stroke-width="2"/><path d="M30 36v-8a10 10 0 0120 0v8" stroke="#f59e0b" stroke-width="2"/></svg>`,

    error: `<svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="40" cy="40" r="40" fill="rgba(239,68,68,0.07)"/><circle cx="40" cy="40" r="16" stroke="#ef4444" stroke-width="2"/><path d="M40 32v12M40 48v2" stroke="#ef4444" stroke-width="2.5" stroke-linecap="round"/></svg>`,

    reviews: `<svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="40" cy="40" r="40" fill="rgba(16,185,129,0.07)"/><path d="M24 26h32v22H24z" rx="2" stroke="#10b981" stroke-width="2"/><path d="M30 52l10 8 10-8" stroke="#10b981" stroke-width="2"/><path d="M32 34h16M32 40h10" stroke="#10b981" stroke-width="2" stroke-linecap="round"/></svg>`,
  },

  render(
    containerEl,
    {
      iconKey = "repos",
      title = "Nothing here yet",
      message = "",
      description = "",
      actionLabel = null,
      actionText = null,
      actionHref = null,
      onAction = null,
    } = {}
  ) {
    if (!containerEl) return;

    const icon = this.ICONS[iconKey] || this.ICONS.repos;
    const bodyMessage = message || description || "";
    const buttonLabel = actionLabel || actionText || null;

    containerEl.innerHTML = `
            <div style="
                display:flex;
                flex-direction:column;
                align-items:center;
                justify-content:center;
                text-align:center;
                padding:4rem 2rem;
                gap:1.25rem;
            ">
                <div style="width:80px;height:80px;" aria-hidden="true">
                    ${icon}
                </div>

                <h3 style="
                    font-size:1.1rem;
                    font-weight:700;
                    color:var(--text-primary);
                ">
                    ${title}
                </h3>

                ${
                  bodyMessage
                    ? `
                    <p style="
                        font-size:0.9rem;
                        color:var(--text-muted);
                        max-width:380px;
                        line-height:1.7;
                    ">
                        ${bodyMessage}
                    </p>
                `
                    : ""
                }

                ${
                  buttonLabel && (onAction || actionHref)
                    ? `
                    ${
                      actionHref && !onAction
                        ? `<a id="empty-state-action" class="btn btn-primary" style="margin-top:.5rem;" href="${actionHref}">${buttonLabel}</a>`
                        : `<button id="empty-state-action" class="btn btn-primary" style="margin-top:.5rem;">${buttonLabel}</button>`
                    }
                `
                    : ""
                }
            </div>
        `;

    if (buttonLabel && onAction) {
      containerEl
        .querySelector("#empty-state-action")
        ?.addEventListener("click", onAction);
    }
  },
};

/**
 * Backward compatibility.
 * Existing files can still use:
 *
 * import { renderEmptyState } from "../components/empty_state.js";
 */
export function renderEmptyState(containerEl, options = {}) {
  return EmptyState.render(containerEl, options);
}

export default EmptyState;
