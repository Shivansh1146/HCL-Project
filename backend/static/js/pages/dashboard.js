/**
 * pages/dashboard.js — Enterprise Dashboard Shell & Command Center.
 *
 * Requirements:
 *  - Responsive grid layout (grid-12)
 *  - Status cards: Connected GitHub, App Status, Selected Repositories, AI Reviews Summary
 *  - Recent Activity section (placeholder)
 *  - Skeleton loaders while fetching real data from API
 *  - Empty states for missing App Installation or Repositories
 *  - Accessible with ARIA labels and semantically structured cards
 */

import { renderEmptyState } from "../components/empty_state.js";
import { renderSkeleton } from "../components/skeleton.js";
import { Toast } from "../components/toast.js";
import { api } from "../services/api.js";
import { dom } from "../utils/dom.js";
import { store } from "../utils/state.js";

/**
 * Renders the main dashboard shell.
 * @param {HTMLElement} outlet
 */
export async function renderDashboardPage(outlet) {
  const { user } = store.getState();
  const safeName = dom.escape(user?.name || user?.login || "Engineer");
  const safeLogin = dom.escape(user?.login || "");

  outlet.innerHTML = "";

  // Wrapper container
  const wrapper = document.createElement("div");
  wrapper.className = "animate-fade-up";
  wrapper.style.cssText = "padding:1rem 0 3rem;";

  // Header Greeting
  const greeting = document.createElement("div");
  greeting.style.cssText = "margin-bottom:2rem;";
  greeting.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem;">
            <div>
                <h1 style="font-size:1.75rem;font-weight:800;letter-spacing:-0.03em;margin-bottom:0.25rem;">
                    Welcome back, ${safeName} 👋
                </h1>
                <p style="color:var(--text-secondary);font-size:0.95rem;">
                    GitHub AI Code Review Command Center & Operational Metrics
                </p>
            </div>
            <div style="display:flex;align-items:center;gap:0.5rem;">
                <span class="status-dot online"></span>
                <span style="font-size:0.85rem;color:var(--text-secondary);font-weight:500;">System Ready</span>
            </div>
        </div>
    `;

  // Metric Grid Container
  const gridContainer = document.createElement("div");
  gridContainer.className = "grid-12";
  gridContainer.id = "dashboard-metric-grid";
  gridContainer.setAttribute("aria-label", "Key Metrics Summary");

  // Render Initial Skeleton Loaders
  gridContainer.innerHTML = `
        <div class="col-span-3">${renderSkeleton("card")}</div>
        <div class="col-span-3">${renderSkeleton("card")}</div>
        <div class="col-span-3">${renderSkeleton("card")}</div>
        <div class="col-span-3">${renderSkeleton("card")}</div>
    `;

  // Activity & Quick Actions Container
  const mainSection = document.createElement("div");
  mainSection.className = "grid-12";
  mainSection.style.cssText = "margin-top:2rem;";
  mainSection.id = "dashboard-main-section";

  mainSection.innerHTML = `
        <div class="col-span-8">${renderSkeleton("card")}</div>
        <div class="col-span-4">${renderSkeleton("card")}</div>
    `;

  wrapper.append(greeting, gridContainer, mainSection);
  outlet.appendChild(wrapper);

  // Fetch Backend Data (Stats + Installations)
  try {
    const [statsData, installationsData, appStatusData, prStatsData] =
      await Promise.allSettled([
        api.getStats(),
        api.getInstallations(),
        api.getAppStatus(),
        api.getPullRequestStats()
      ]);

    const stats = statsData.status === "fulfilled" ? statsData.value : {};
    const installations =
      installationsData.status === "fulfilled" &&
      Array.isArray(installationsData.value)
        ? installationsData.value
        : [];
    const appStatus =
      appStatusData.status === "fulfilled" ? appStatusData.value : null;
    const installUrl = appStatus?.install_url || "";
    
    // Use PR stats for AI review counts to match Review History consistency
    const prStats = prStatsData.status === "fulfilled" ? prStatsData.value : {};

    store.setInstallations(installations);

    const hasInstallations = installations.length > 0;
    const totalSelectedRepos =
      stats?.selected_repos_count ?? stats?.monitored_repositories_count ?? 0;
    // Use AI review count from /api/prs/stats for consistency
    const totalReviews = prStats?.total_reviews ?? stats?.total_reviews ?? 0;

    // --- Render Real Metrics Grid ---
    gridContainer.innerHTML = `
            <!-- Card 1: GitHub Connection Status -->
            <div class="glass-card stat-card col-span-3 animate-fade-up animate-fade-up-delay-1">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.75rem;">
                    <span class="stat-card-label">GitHub Account</span>
                    <span class="badge badge-success" style="font-size:0.7rem;">Connected</span>
                </div>
                <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem;">
                    <img src="${dom.safeUrl(
                      user?.avatar_url || ""
                    )}" alt="${safeLogin} avatar"
                         style="width:32px;height:32px;border-radius:50%;border:1px solid var(--border-color);"
                         onerror="this.src='https://github.com/ghost.png'">
                    <span style="font-weight:700;font-size:1.1rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                        @${safeLogin}
                    </span>
                </div>
                <p class="stat-card-sub">OAuth 2.0 Scope Verified</p>
            </div>

            <!-- Card 2: GitHub App Installation Status -->
            <div class="glass-card stat-card col-span-3 animate-fade-up animate-fade-up-delay-2">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.75rem;">
                    <span class="stat-card-label">GitHub App Status</span>
                    <span class="badge ${
                      hasInstallations ? "badge-success" : "badge-warning"
                    }" style="font-size:0.7rem;">
                        ${hasInstallations ? "Installed" : "Action Required"}
                    </span>
                </div>
                <div class="stat-card-value">${installations.length}</div>
                <p class="stat-card-sub">${
                  hasInstallations
                    ? "Active App Installation(s)"
                    : "No App installed yet"
                }</p>
            </div>

            <!-- Card 3: Selected Repositories -->
            <div class="glass-card stat-card col-span-3 animate-fade-up animate-fade-up-delay-3">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.75rem;">
                    <span class="stat-card-label">Selected Repos</span>
                    <span class="badge badge-primary" style="font-size:0.7rem;">Monitored</span>
                </div>
                <div class="stat-card-value">${totalSelectedRepos}</div>
                <p class="stat-card-sub">Active for Automated AI Review</p>
            </div>

            <!-- Card 4: AI Reviews Conducted -->
            <div class="glass-card stat-card col-span-3 animate-fade-up animate-fade-up-delay-4">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.75rem;">
                    <span class="stat-card-label">AI PR Reviews</span>
                    <span class="badge badge-info" style="font-size:0.7rem;">Groq Llama-3</span>
                </div>
                <div class="stat-card-value">${totalReviews}</div>
                <p class="stat-card-sub">Automated Code Reviews Completed</p>
            </div>
        `;

    // --- Render Main Content Section ---
    mainSection.innerHTML = "";

    if (!hasInstallations) {
      // Empty State: App not installed
      const emptyCol = document.createElement("div");
      emptyCol.className = "col-span-12";
      renderEmptyState(emptyCol, {
        title: "GitHub App Not Installed",
        description: appStatus?.configured
          ? "Install the GitHub App on your account or organization to start monitoring pull requests with AI."
          : "GitHub App credentials are not fully configured yet. Add the missing app settings, then install the app to start monitoring pull requests with AI.",
        icon: `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/></svg>`,
        actionText: "Install GitHub App",
        onAction: async () => {
          if (installUrl) {
            window.location.href = installUrl;
            return;
          }
          Toast.error("GitHub App installation URL is not configured.");
        },
      });
      mainSection.appendChild(emptyCol);
    } else {
      // Main Dashboard Overview Cards
      const activityCard = document.createElement("div");
      activityCard.className = "glass-card col-span-8";
      activityCard.innerHTML = `
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.5rem;">
                    <h2 style="font-size:1.1rem;font-weight:700;">Recent AI Code Reviews</h2>
                    <a href="#/repositories" class="btn btn-ghost" style="font-size:0.85rem;">View Repositories →</a>
                </div>
                <div style="display:flex;flex-direction:column;gap:1rem;">
                    <div style="padding:1rem;background:rgba(255,255,255,0.02);border:1px solid var(--border-color);border-radius:var(--radius-md);display:flex;align-items:center;justify-content:space-between;">
                        <div style="display:flex;align-items:center;gap:0.75rem;">
                            <div style="width:10px;height:10px;border-radius:50%;background:var(--color-success);"></div>
                            <div>
                                <h4 style="font-size:0.9rem;font-weight:600;">System Webhook Listener Active</h4>
                                <p style="font-size:0.75rem;color:var(--text-muted);">Awaiting incoming pull request events from GitHub App</p>
                            </div>
                        </div>
                        <span class="badge badge-success" style="font-size:0.7rem;">Listening</span>
                    </div>
                </div>
            `;

      const quickActionsCard = document.createElement("div");
      quickActionsCard.className = "glass-card col-span-4";
      quickActionsCard.innerHTML = `
                <h2 style="font-size:1.1rem;font-weight:700;margin-bottom:1.25rem;">Quick Actions</h2>
                <div style="display:flex;flex-direction:column;gap:0.75rem;">
                    <a href="#/repositories" class="btn btn-secondary" style="width:100%;justify-content:flex-start;gap:0.5rem;">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3h18v18H3zM3 9h18M9 21V9"/></svg>
                        Manage Repositories
                    </a>
                    <a href="#/profile" class="btn btn-secondary" style="width:100%;justify-content:flex-start;gap:0.5rem;">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                        View Account Profile
                    </a>
                    <a href="#/settings" class="btn btn-secondary" style="width:100%;justify-content:flex-start;gap:0.5rem;">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/></svg>
                        Review Settings
                    </a>
                </div>
            `;

      mainSection.append(activityCard, quickActionsCard);
    }
  } catch (err) {
    console.error("[Dashboard] Error loading dashboard data:", err);
    Toast.error("Failed to load dashboard metrics.");
  }
}
