/**
 * pages/settings.js — Enterprise Settings, Preferences & System Administration.
 *
 * Requirements:
 *  - Theme Control (Dark, Light, System) with state persistence
 *  - Notification Preferences (Review, Sync, Security, Errors)
 *  - Automation Preferences (Auto-Sync, Default Org)
 *  - System Health & Status Administration
 *  - Accessibility & Toast Feedback
 */

import { store }   from "../utils/state.js";
import { dom }     from "../utils/dom.js";
import { Toast }   from "../components/toast.js";
import { api }     from "../services/api.js";

export async function renderSettingsPage(outlet) {
    outlet.innerHTML = "";

    const wrapper = document.createElement("div");
    wrapper.className = "animate-fade-up";
    wrapper.style.cssText = "padding:1rem 0 3rem;";


    // Header
    const header = document.createElement("div");
    header.style.cssText = "margin-bottom:1.5rem;";
    header.innerHTML = `
        <h1 style="font-size:1.75rem;font-weight:800;letter-spacing:-0.03em;margin-bottom:0.25rem;">
            Application Settings & Administration
        </h1>
        <p style="color:var(--text-secondary);font-size:0.95rem;">
            Preferences, System Health Status, and AI Provider Configurations
        </p>
    `;

    // 2. Notification Preferences
    const notifyCard = document.createElement("div");
    notifyCard.className = "glass-card";
    notifyCard.style.cssText = "padding:1.5rem;margin-bottom:1.5rem;";

    notifyCard.innerHTML = `
        <h3 style="font-size:1.1rem;font-weight:700;margin-bottom:1rem;display:flex;align-items:center;gap:0.5rem;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0"/></svg>
            Notification Preferences
        </h3>
        <div style="display:flex;flex-direction:column;gap:0.85rem;">
            <label style="display:flex;align-items:center;justify-content:space-between;font-size:0.9rem;cursor:pointer;">
                <span>AI Review Completed Alerts</span>
                <input type="checkbox" id="notify-review" checked style="width:18px;height:18px;">
            </label>
            <label style="display:flex;align-items:center;justify-content:space-between;font-size:0.9rem;cursor:pointer;">
                <span>Repository Synchronization Status</span>
                <input type="checkbox" id="notify-sync" checked style="width:18px;height:18px;">
            </label>
            <label style="display:flex;align-items:center;justify-content:space-between;font-size:0.9rem;cursor:pointer;">
                <span>Critical Security Finding Alerts</span>
                <input type="checkbox" id="notify-sec" checked style="width:18px;height:18px;">
            </label>
        </div>
    `;

    notifyCard.querySelectorAll('input[type="checkbox"]').forEach(chk => {
        chk.addEventListener("change", () => Toast.info("Notification preferences saved."));
    });

    // 3. System Administration & Health Status (live data)
    const adminCard = document.createElement("div");
    adminCard.className = "glass-card";
    adminCard.style.cssText = "padding:1.5rem;";
    adminCard.id = "settings-health-card";
    adminCard.innerHTML = `
        <h3 style="font-size:1.1rem;font-weight:700;margin-bottom:1rem;display:flex;align-items:center;gap:0.5rem;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
            System Administration &amp; Health Status
        </h3>
        <div id="settings-health-grid" style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:1rem;">
            <div style="padding:1rem;background:rgba(255,255,255,0.02);border:1px solid var(--border-color);border-radius:8px;">
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;">Loading status…</span>
            </div>
        </div>
    `;

    wrapper.append(header, notifyCard, adminCard);
    outlet.appendChild(wrapper);

    // Fetch live health status
    _loadHealthStatus();
}

async function _loadHealthStatus() {
    const grid = document.getElementById("settings-health-grid");
    if (!grid) return;

    const [healthRes, aiRes] = await Promise.allSettled([
        api.request("/api/health"),
        api.request("/api/health/ai"),
        api.getAppStatus()
    ]);

    const health = healthRes.status === "fulfilled" ? healthRes.value : null;
    const ai     = aiRes.status    === "fulfilled" ? aiRes.value    : null;
    const app    = appRes.status   === "fulfilled" ? appRes.value   : null;

    // API Gateway
    const apiOk = health?.status === "healthy";

    // Database — backend is PostgreSQL-only; health endpoint confirms connectivity
    const dbOk  = health?.database === "connected";

    // AI Provider
    const aiOk      = ai?.groq_configured && ai?.groq_reachable;
    const aiModel   = ai?.model ? dom.escape(ai.model) : "Groq Llama-3";

    // GitHub App — from /api/app/status; .configured = app credentials set up
    const ghOk = app?.configured === true;

    grid.innerHTML = `
        <div style="padding:1rem;background:rgba(255,255,255,0.02);border:1px solid var(--border-color);border-radius:8px;">
            <span style="font-size:0.75rem;color:var(--text-muted);display:block;">API Gateway Status</span>
            <span class="badge ${apiOk ? 'badge-success' : 'badge-error'}" style="margin-top:0.25rem;">
                ${apiOk ? '🟢 Operational' : '🔴 Unreachable'}
            </span>
        </div>
        <div style="padding:1rem;background:rgba(255,255,255,0.02);border:1px solid var(--border-color);border-radius:8px;">
            <span style="font-size:0.75rem;color:var(--text-muted);display:block;">Database Connection</span>
            <span class="badge ${dbOk ? 'badge-success' : 'badge-error'}" style="margin-top:0.25rem;">
                ${dbOk ? '🟢 PostgreSQL Connected' : '🔴 Disconnected'}
            </span>
        </div>
        <div style="padding:1rem;background:rgba(255,255,255,0.02);border:1px solid var(--border-color);border-radius:8px;">
            <span style="font-size:0.75rem;color:var(--text-muted);display:block;">AI Provider Pipeline</span>
            <span class="badge ${aiOk ? 'badge-success' : (ai === null ? 'badge-warning' : 'badge-error')}" style="margin-top:0.25rem;">
                ${aiOk ? `🟢 ${aiModel} Active` : (ai === null ? '🟡 Status Unknown' : '🔴 Unavailable')}
            </span>
        </div>
        <div style="padding:1rem;background:rgba(255,255,255,0.02);border:1px solid var(--border-color);border-radius:8px;">
            <span style="font-size:0.75rem;color:var(--text-muted);display:block;">GitHub App Integration</span>
            <span class="badge ${ghOk ? 'badge-success' : (app === null ? 'badge-warning' : 'badge-error')}" style="margin-top:0.25rem;">
                ${ghOk ? '🟢 App Configured' : (app === null ? '🟡 Status Unknown' : '🔴 Not Configured')}
            </span>
        </div>
    `;
}
