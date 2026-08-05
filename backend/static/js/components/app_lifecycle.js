/**
 * app_lifecycle.js — Enterprise GitHub App Lifecycle & Synchronization Manager.
 *
 * Components:
 *  1. GitHub App Status Card (Installed, Suspended, Needs Sync, Installation ID)
 *  2. Installation Wizard (Guided setup banner with permissions & security overview)
 *  3. Sync Manager (Handles manual sync, progress indicators, and store updates)
 *  4. Health Indicator (Healthy, Needs Sync, Token Expired, Suspended)
 *
 * Security:
 *  - Never exposes JWTs, private keys, or installation tokens.
 *  - All user/org strings escaped via dom.escape().
 */

import { dom } from "../utils/dom.js";
import { Toast } from "./toast.js";

/**
 * Calculates health status badge object for an installation.
 * @param {Object} inst
 * @returns {{ status: string, label: string, color: string, badgeClass: string }}
 */
export function getInstallationHealth(inst) {
  if (!inst) {
    return {
      status: "not_installed",
      label: "Not Installed",
      color: "#f59e0b",
      badgeClass: "badge-warning",
    };
  }

  if (inst.status === "suspended") {
    return {
      status: "suspended",
      label: "Suspended",
      color: "#ef4444",
      badgeClass: "badge-error",
    };
  }

  if (inst.status === "active") {
    return {
      status: "healthy",
      label: "Healthy",
      color: "#10b981",
      badgeClass: "badge-success",
    };
  }

  return {
    status: "needs_sync",
    label: "Needs Sync",
    color: "#3b82f6",
    badgeClass: "badge-info",
  };
}

/**
 * Renders the GitHub App Status Card.
 * @param {HTMLElement} mountEl
 * @param {Object} installation
 * @param {() => Promise<void>} onSync
 * @param {string} installUrl
 */
export function renderAppStatusCard(
  mountEl,
  installation,
  onSync,
  installUrl = ""
) {
  if (!mountEl) return;

  mountEl.innerHTML = "";
  const health = getInstallationHealth(installation);
  const safeInstallUrl = dom.safeUrl(installUrl || "");

  const card = document.createElement("div");
  card.className = "glass-card animate-fade-up";
  card.style.cssText =
    "padding:1.5rem;display:flex;flex-direction:column;gap:1rem;";

  if (!installation) {
    // Render Installation Wizard
    renderInstallationWizard(card, installUrl);
    mountEl.appendChild(card);
    return;
  }

  const safeLogin = dom.escape(installation.account_login || "Account");
  const safeType = dom.escape(installation.account_type || "User");

  card.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem;">
            <div style="display:flex;align-items:center;gap:0.75rem;">
                <div style="width:40px;height:40px;border-radius:10px;background:rgba(59,130,246,0.15);color:var(--primary);display:flex;align-items:center;justify-content:center;" aria-hidden="true">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/></svg>
                </div>
                <div>
                    <h3 style="font-size:1.05rem;font-weight:700;">GitHub App Health & Lifecycle</h3>
                    <p style="font-size:0.8rem;color:var(--text-muted);">Connected Target: <strong>${safeLogin}</strong> (${safeType})</p>
                </div>
            </div>
            <div style="display:flex;align-items:center;gap:0.5rem;">
                <span class="badge ${
                  health.badgeClass
                }" style="font-size:0.8rem;">● ${health.label}</span>
            </div>
        </div>

        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:1rem;padding:1rem;background:rgba(255,255,255,0.02);border:1px solid var(--border-color);border-radius:var(--radius-md);">
            <div>
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;">Installation ID</span>
                <strong style="font-size:0.95rem;">${
                  installation.installation_id
                }</strong>
            </div>
            <div>
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;">Target Account</span>
                <strong style="font-size:0.95rem;">${safeLogin}</strong>
            </div>
            <div>
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;">Account Type</span>
                <strong style="font-size:0.95rem;">${safeType}</strong>
            </div>
            <div>
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;">Sync Status</span>
                <strong style="font-size:0.95rem;color:var(--color-success);">Synchronized</strong>
            </div>
        </div>

        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem;margin-top:0.5rem;">
            <p style="font-size:0.8rem;color:var(--text-secondary);">
                Webhook listener is active. Repository permissions and push events sync automatically.
            </p>
            <div style="display:flex;align-items:center;gap:0.75rem;">
                <button type="button" id="app-sync-trigger-btn" class="btn btn-secondary" style="gap:0.5rem;">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 11-.57-8.38l5.67-5.67"/></svg>
                    <span>Force Sync Now</span>
                </button>
                ${
                  safeInstallUrl !== "#"
                    ? `<a href="${safeInstallUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-ghost" style="font-size:0.85rem;">Configure Permissions ↗</a>`
                    : ""
                }
            </div>
        </div>
    `;

  const syncBtn = card.querySelector("#app-sync-trigger-btn");
  syncBtn?.addEventListener("click", async () => {
    syncBtn.disabled = true;
    syncBtn.innerHTML = `<div class="spinner" style="width:14px;height:14px;"></div> Syncing…`;
    try {
      if (onSync) await onSync();
      Toast.success(
        `Successfully synchronized installation ${installation.installation_id}`
      );
    } catch (err) {
      Toast.error(err?.message || "Sync failed.");
    } finally {
      syncBtn.disabled = false;
      syncBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 11-.57-8.38l5.67-5.67"/></svg> <span>Force Sync Now</span>`;
    }
  });

  mountEl.appendChild(card);
}

/**
 * Renders guided Installation Wizard for uninstalled states.
 * @param {HTMLElement} container
 * @param {string} installUrl
 */
export function renderInstallationWizard(container, installUrl = "") {
  const safeInstallUrl = dom.safeUrl(installUrl || "");
  container.innerHTML = `
        <div style="text-align:center;padding:1.5rem 1rem;">
            <div style="width:54px;height:54px;background:linear-gradient(135deg,#3b82f6,#8b5cf6);border-radius:14px;display:flex;align-items:center;justify-content:center;margin:0 auto 1.25rem;box-shadow:0 8px 24px rgba(59,130,246,0.35);" aria-hidden="true">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="white"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/></svg>
            </div>
            <h2 style="font-size:1.3rem;font-weight:800;letter-spacing:-0.02em;margin-bottom:0.5rem;">
                Install GitHub App to Enable AI Code Review
            </h2>
            <p style="font-size:0.9rem;color:var(--text-secondary);max-width:500px;margin:0 auto 1.5rem;line-height:1.6;">
                To allow our AI engine to automatically review Pull Requests and leave inline security analysis, install the official GitHub App on your account or organization.
            </p>

            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:1rem;margin-bottom:2rem;text-align:left;">
                <div style="padding:1rem;background:rgba(255,255,255,0.02);border:1px solid var(--border-color);border-radius:10px;">
                    <h4 style="font-size:0.85rem;font-weight:700;margin-bottom:0.25rem;color:var(--primary);">🔒 Read PR & Code</h4>
                    <p style="font-size:0.75rem;color:var(--text-muted);">Access code diffs to analyze potential security and performance issues.</p>
                </div>
                <div style="padding:1rem;background:rgba(255,255,255,0.02);border:1px solid var(--border-color);border-radius:10px;">
                    <h4 style="font-size:0.85rem;font-weight:700;margin-bottom:0.25rem;color:var(--color-success);">💬 Post PR Comments</h4>
                    <p style="font-size:0.75rem;color:var(--text-muted);">Automatically post code review suggestions directly onto open PRs.</p>
                </div>
                <div style="padding:1rem;background:rgba(255,255,255,0.02);border:1px solid var(--border-color);border-radius:10px;">
                    <h4 style="font-size:0.85rem;font-weight:700;margin-bottom:0.25rem;color:var(--color-info);">🛡️ Zero Token Storage</h4>
                    <p style="font-size:0.75rem;color:var(--text-muted);">Short-lived installation tokens are generated on-the-fly and never stored on disk.</p>
                </div>
            </div>

            ${
              safeInstallUrl !== "#"
                ? `<a href="${safeInstallUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-github" style="padding:0.75rem 2rem;font-size:1rem;font-weight:700;">Install GitHub App Now ↗</a>`
                : `<div style="padding:0.9rem 1rem;border:1px solid var(--border-color);border-radius:10px;color:var(--text-secondary);font-size:0.9rem;line-height:1.6;max-width:540px;margin:0 auto;">
                    Set GITHUB_APP_INSTALL_URL, GITHUB_APP_SLUG, or GITHUB_APP_NAME so the app can generate an install link.
                </div>`
            }
        </div>
    `;
}
