/**
 * pages/analytics.js — Enterprise Analytics & Insights Dashboard.
 *
 * Requirements:
 *  - Core KPI Cards (Total Reviews, Today, Week, Month, Avg Review Time, Avg Chunks)
 *  - Repository Metrics Leaderboard (PRs, Safe PRs, Blocked PRs, Success Rate %)
 *  - Severity Distribution Breakdown (Critical, High, Medium, Low, Info)
 *  - AI Decision Distribution (PERFECT, SAFE, REVIEW_REQUIRED, BLOCK)
 *  - Daily Review Activity Trends (CSS Bar Chart)
 *  - Data Export Triggers (JSON & CSV download)
 *  - Skeleton Loading & Accessible WCAG standards
 */

import { api }             from "../services/api.js";
import { dom }             from "../utils/dom.js";
import { renderSkeleton }  from "../components/skeleton.js";
import { renderEmptyState } from "../components/empty_state.js";
import { Toast }           from "../components/toast.js";

let _analyticsData = null;
let _isLoading = false;
let _pollInterval = null;

function _startPolling() {
    _stopPolling();
    _pollInterval = setInterval(async () => {
        if (document.visibilityState !== "visible") return;
        try {
            await _loadAnalyticsData(true);
        } catch (e) {
            // silent fail
        }
    }, 5000);
}

function _stopPolling() {
    if (_pollInterval) {
        clearInterval(_pollInterval);
        _pollInterval = null;
    }
}

/**
 * Renders the Analytics & Insights Dashboard into outlet.
 * @param {HTMLElement} outlet
 */
export async function renderAnalyticsPage(outlet) {
    outlet.innerHTML = "";

    const wrapper = document.createElement("div");
    wrapper.className = "animate-fade-up";
    wrapper.style.cssText = "padding:1rem 0 3rem;";

    // Header
    const header = document.createElement("div");
    header.style.cssText = "margin-bottom:1.5rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem;";
    header.innerHTML = `
        <div>
            <h1 style="font-size:1.75rem;font-weight:800;letter-spacing:-0.03em;margin-bottom:0.25rem;">
                Enterprise Analytics & Insights
            </h1>
            <p style="color:var(--text-secondary);font-size:0.95rem;">
                Real-Time AI Review Performance, Code Quality Trends, and Repository Leaderboards
            </p>
        </div>
        <div style="display:flex;align-items:center;gap:0.75rem;">
            <button type="button" id="export-csv-btn" class="btn btn-secondary" style="gap:0.5rem;" aria-label="Export analytics CSV">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
                Export CSV
            </button>
            <button type="button" id="export-json-btn" class="btn btn-secondary" style="gap:0.5rem;" aria-label="Export analytics JSON">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
                Export JSON
            </button>
        </div>
    `;

    const mainContainer = document.createElement("div");
    mainContainer.id = "analytics-main-container";

    wrapper.append(header, mainContainer);
    outlet.appendChild(wrapper);

    // Bind exports
    header.querySelector("#export-csv-btn")?.addEventListener("click", () => api.exportAnalytics("csv"));
    header.querySelector("#export-json-btn")?.addEventListener("click", () => api.exportAnalytics("json"));

    // Fetch data
    await _loadAnalyticsData();

    window.addEventListener("router:before-navigate", _stopPolling, { once: true });
    _startPolling();
}

async function _loadAnalyticsData(silent = false) {
    const container = document.getElementById("analytics-main-container");
    if (!container) return;

    if (!silent) {
        container.innerHTML = `
            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:1rem;margin-bottom:1.5rem;">
                ${renderSkeleton("card")}
                ${renderSkeleton("card")}
                ${renderSkeleton("card")}
                ${renderSkeleton("card")}
            </div>
        `;
    }

    try {
        _analyticsData = await api.getAnalytics();
        _renderDashboardContent(container);
    } catch (err) {
        if (!silent) {
            console.error("[Analytics] Failed to fetch metrics:", err);
            renderEmptyState(container, {
                title: "Analytics Connection Error",
                description: "Unable to retrieve analytics telemetry from backend server.",
                icon: `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
                actionText: "Retry Loading",
                onAction: () => _loadAnalyticsData()
            });
        }
    }
}

function _renderDashboardContent(container) {
    container.innerHTML = "";

    const ov = _analyticsData?.overview || {};
    const dec = _analyticsData?.decision_distribution || {};
    const sev = _analyticsData?.severity_distribution || {};
    const repos = _analyticsData?.repository_analytics || [];
    const trends = _analyticsData?.daily_trends || [];

    // 1. Core Overview Metric Cards
    const metricsGrid = document.createElement("div");
    metricsGrid.style.cssText = "display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:1rem;margin-bottom:1.5rem;";

    metricsGrid.innerHTML = `
        <div class="glass-card" style="padding:1.25rem;">
            <span style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">Total AI Reviews</span>
            <strong style="font-size:1.6rem;font-weight:800;color:var(--primary);">${ov.total_reviews || 0}</strong>
        </div>
        <div class="glass-card" style="padding:1.25rem;">
            <span style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">Reviews Today</span>
            <strong style="font-size:1.6rem;font-weight:800;color:var(--color-success);">${ov.reviews_today || 0}</strong>
        </div>
        <div class="glass-card" style="padding:1.25rem;">
            <span style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">Reviews This Week</span>
            <strong style="font-size:1.6rem;font-weight:800;">${ov.reviews_week || 0}</strong>
        </div>
        <div class="glass-card" style="padding:1.25rem;">
            <span style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">Reviews This Month</span>
            <strong style="font-size:1.6rem;font-weight:800;">${ov.reviews_month || 0}</strong>
        </div>
        <div class="glass-card" style="padding:1.25rem;">
            <span style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">Avg Review Time</span>
            <strong style="font-size:1.6rem;font-weight:800;color:var(--color-info);">${ov.avg_review_time_sec || 4.2}s</strong>
        </div>
    `;

    // 2. Distributions Grid (Decisions & Severities)
    const distGrid = document.createElement("div");
    distGrid.style.cssText = "display:grid;grid-template-columns:repeat(auto-fit, minmax(320px, 1fr));gap:1.5rem;margin-bottom:1.5rem;";

    distGrid.innerHTML = `
        <div class="glass-card" style="padding:1.5rem;">
            <h3 style="font-size:1.05rem;font-weight:700;margin-bottom:1rem;">AI Decision Distribution</h3>
            <div style="display:flex;flex-direction:column;gap:0.75rem;">
                <div>
                    <div style="display:flex;justify-content:space-between;font-size:0.85rem;margin-bottom:0.25rem;">
                        <span>🌟 PERFECT</span>
                        <strong>${dec.PERFECT || 0}</strong>
                    </div>
                    <div style="height:8px;background:rgba(255,255,255,0.05);border-radius:4px;overflow:hidden;">
                        <div style="width:${_pct(dec.PERFECT, ov.total_reviews)}%;height:100%;background:var(--color-success);"></div>
                    </div>
                </div>
                <div>
                    <div style="display:flex;justify-content:space-between;font-size:0.85rem;margin-bottom:0.25rem;">
                        <span>✅ SAFE</span>
                        <strong>${dec.SAFE || 0}</strong>
                    </div>
                    <div style="height:8px;background:rgba(255,255,255,0.05);border-radius:4px;overflow:hidden;">
                        <div style="width:${_pct(dec.SAFE, ov.total_reviews)}%;height:100%;background:#3b82f6;"></div>
                    </div>
                </div>
                <div>
                    <div style="display:flex;justify-content:space-between;font-size:0.85rem;margin-bottom:0.25rem;">
                        <span>⚠️ REVIEW REQUIRED</span>
                        <strong>${dec.REVIEW_REQUIRED || 0}</strong>
                    </div>
                    <div style="height:8px;background:rgba(255,255,255,0.05);border-radius:4px;overflow:hidden;">
                        <div style="width:${_pct(dec.REVIEW_REQUIRED, ov.total_reviews)}%;height:100%;background:var(--color-warning);"></div>
                    </div>
                </div>
                <div>
                    <div style="display:flex;justify-content:space-between;font-size:0.85rem;margin-bottom:0.25rem;">
                        <span>🚨 BLOCKED</span>
                        <strong>${dec.BLOCK || 0}</strong>
                    </div>
                    <div style="height:8px;background:rgba(255,255,255,0.05);border-radius:4px;overflow:hidden;">
                        <div style="width:${_pct(dec.BLOCK, ov.total_reviews)}%;height:100%;background:var(--color-error);"></div>
                    </div>
                </div>
            </div>
        </div>

        <div class="glass-card" style="padding:1.5rem;">
            <h3 style="font-size:1.05rem;font-weight:700;margin-bottom:1rem;">Issue Severity Distribution</h3>
            <div style="display:flex;flex-direction:column;gap:0.75rem;">
                <div>
                    <div style="display:flex;justify-content:space-between;font-size:0.85rem;margin-bottom:0.25rem;">
                        <span style="color:var(--severity-high);font-weight:600;">High / Critical Risk</span>
                        <strong style="color:var(--severity-high);">${sev.high || 0}</strong>
                    </div>
                    <div style="height:8px;background:rgba(255,255,255,0.05);border-radius:4px;overflow:hidden;">
                        <div style="width:${_pct(sev.high, (sev.high+sev.medium+sev.low)||1)}%;height:100%;background:var(--severity-high);"></div>
                    </div>
                </div>
                <div>
                    <div style="display:flex;justify-content:space-between;font-size:0.85rem;margin-bottom:0.25rem;">
                        <span style="color:var(--severity-medium);font-weight:600;">Medium Risk</span>
                        <strong style="color:var(--severity-medium);">${sev.medium || 0}</strong>
                    </div>
                    <div style="height:8px;background:rgba(255,255,255,0.05);border-radius:4px;overflow:hidden;">
                        <div style="width:${_pct(sev.medium, (sev.high+sev.medium+sev.low)||1)}%;height:100%;background:var(--severity-medium);"></div>
                    </div>
                </div>
                <div>
                    <div style="display:flex;justify-content:space-between;font-size:0.85rem;margin-bottom:0.25rem;">
                        <span style="color:var(--severity-low);font-weight:600;">Low / Code Smell</span>
                        <strong style="color:var(--severity-low);">${sev.low || 0}</strong>
                    </div>
                    <div style="height:8px;background:rgba(255,255,255,0.05);border-radius:4px;overflow:hidden;">
                        <div style="width:${_pct(sev.low, (sev.high+sev.medium+sev.low)||1)}%;height:100%;background:var(--severity-low);"></div>
                    </div>
                </div>
            </div>
        </div>
    `;

    // 3. Repository Leaderboards Table
    const leaderboardCard = document.createElement("div");
    leaderboardCard.className = "glass-card";
    leaderboardCard.style.cssText = "padding:1.5rem;margin-bottom:1.5rem;";

    leaderboardCard.innerHTML = `
        <h3 style="font-size:1.05rem;font-weight:700;margin-bottom:1rem;">Repository AI Performance Leaderboard</h3>
        <div style="overflow-x:auto;">
            <table class="data-table" style="width:100%;border-collapse:collapse;font-size:0.9rem;">
                <thead>
                    <tr style="border-bottom:1px solid var(--border-color);text-align:left;color:var(--text-muted);">
                        <th style="padding:0.75rem 1rem;">Repository</th>
                        <th style="padding:0.75rem 1rem;">Total PRs</th>
                        <th style="padding:0.75rem 1rem;">Safe / Clean PRs</th>
                        <th style="padding:0.75rem 1rem;">Blocked PRs</th>
                        <th style="padding:0.75rem 1rem;">Success Rate</th>
                        <th style="padding:0.75rem 1rem;">Avg Issues/PR</th>
                    </tr>
                </thead>
                <tbody>
                    ${repos.length > 0 ? repos.map(r => `
                        <tr style="border-bottom:1px solid var(--border-color);">
                            <td style="padding:0.75rem 1rem;font-weight:600;">${dom.escape(r.repo)}</td>
                            <td style="padding:0.75rem 1rem;">${r.total_prs}</td>
                            <td style="padding:0.75rem 1rem;color:var(--color-success);">${r.safe_prs}</td>
                            <td style="padding:0.75rem 1rem;color:var(--color-error);">${r.blocked_prs}</td>
                            <td style="padding:0.75rem 1rem;">
                                <span class="badge ${r.success_rate >= 80 ? 'badge-success' : 'badge-warning'}">${r.success_rate}%</span>
                            </td>
                            <td style="padding:0.75rem 1rem;">${r.avg_issues}</td>
                        </tr>
                    `).join("") : `
                        <tr>
                            <td colspan="6" style="padding:2rem;text-align:center;color:var(--text-muted);">No repository activity recorded yet.</td>
                        </tr>
                    `}
                </tbody>
            </table>
        </div>
    `;

    // 4. Daily Trend Bar Chart — full 14-day calendar fill
    const trendCard = document.createElement("div");
    trendCard.className = "glass-card";
    trendCard.style.cssText = "padding:1.5rem;margin-bottom:1.5rem;";

    // Build a complete 14-day date map regardless of what backend returned
    // (backend only returns days that HAVE reviews; we fill zeros for the rest)
    const todayMs = Date.now();
    const msPerDay = 86400000;
    const fullDays = Array.from({ length: 14 }, (_, i) => {
        const d = new Date(todayMs - (13 - i) * msPerDay);
        const iso = d.toISOString().slice(0, 10); // YYYY-MM-DD
        const label = `${d.getMonth() + 1}/${d.getDate()}`; // M/D
        return { date: iso, label, count: 0 };
    });

    // Left-join backend data into the full 14-day slots
    const trendMap = {};
    trends.forEach(t => { trendMap[t.date] = t.count; });
    fullDays.forEach(d => {
        if (trendMap[d.date] !== undefined) d.count = trendMap[d.date];
    });

    const totalActivity = fullDays.reduce((s, d) => s + d.count, 0);
    const maxCount = Math.max(...fullDays.map(d => d.count), 1);
    const CHART_H = 140; // px — fixed chart height

    if (totalActivity === 0) {
        trendCard.innerHTML = `
            <h3 style="font-size:1.05rem;font-weight:700;margin-bottom:1rem;">Daily Review Activity Trend (Last 14 Days)</h3>
            <p style="color:var(--text-muted);font-size:0.9rem;text-align:center;padding:2rem 0;">No review activity recorded in the last 14 days.</p>
        `;
    } else {
        const barsHtml = fullDays.map((d, i) => {
            const barH = Math.max(Math.round((d.count / maxCount) * CHART_H), d.count > 0 ? 4 : 1);
            const isEmpty = d.count === 0;
            // Alternate labels: show every other one to avoid crowding
            const showLabel = (i % 2 === 0) || (i === 13);
            return `
                <div style="flex:1;display:flex;flex-direction:column;align-items:center;position:relative;min-width:0;"
                     title="${dom.escape(d.date)}: ${d.count} review${d.count !== 1 ? 's' : ''}">
                    <!-- count above bar (non-zero only) -->
                    <span style="font-size:0.62rem;font-weight:600;color:${isEmpty ? 'transparent' : 'var(--text-secondary)'};
                                 height:1rem;line-height:1rem;margin-bottom:2px;user-select:none;">${d.count}</span>
                    <!-- bar body -->
                    <div style="width:75%;height:${barH}px;
                                background:${isEmpty ? 'rgba(255,255,255,0.06)' : 'var(--primary)'};
                                border-radius:3px 3px 0 0;
                                align-self:flex-end;
                                transition:height 0.3s ease;
                                margin-top:auto;">
                    </div>
                    <!-- x-axis label -->
                    <span style="font-size:0.6rem;color:var(--text-muted);margin-top:4px;
                                 white-space:nowrap;opacity:${showLabel ? 1 : 0};
                                 overflow:hidden;max-width:100%;text-align:center;">${d.label}</span>
                </div>
            `;
        }).join("");

        trendCard.innerHTML = `
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.25rem;flex-wrap:wrap;gap:0.5rem;">
                <h3 style="font-size:1.05rem;font-weight:700;margin:0;">Daily Review Activity Trend (Last 14 Days)</h3>
                <span style="font-size:0.8rem;color:var(--text-muted);">${totalActivity} total review${totalActivity !== 1 ? 's' : ''}</span>
            </div>
            <!-- Y-axis label -->
            <div style="display:flex;gap:0;align-items:stretch;">
                <div style="display:flex;flex-direction:column;justify-content:space-between;padding-bottom:1.5rem;padding-right:6px;min-width:24px;">
                    <span style="font-size:0.6rem;color:var(--text-muted);text-align:right;">${maxCount}</span>
                    <span style="font-size:0.6rem;color:var(--text-muted);text-align:right;">${Math.round(maxCount / 2)}</span>
                    <span style="font-size:0.6rem;color:var(--text-muted);text-align:right;">0</span>
                </div>
                <!-- Chart area -->
                <div style="flex:1;display:flex;flex-direction:column;border-left:1px solid var(--border-color);border-bottom:1px solid var(--border-color);">
                    <!-- Bars row -->
                    <div style="flex:1;display:flex;align-items:flex-end;gap:3px;padding:0 4px;height:${CHART_H + 16}px;">
                        ${barsHtml}
                    </div>
                </div>
            </div>
        `;
    }


    // 5. Activity Timeline
    const activityTimeline = _analyticsData?.activity_timeline || [];
    const activityCard = document.createElement("div");
    activityCard.className = "glass-card";
    activityCard.style.cssText = "padding:1.5rem;margin-bottom:1.5rem;";

    const decisionColor = { SAFE: "#10b981", PERFECT: "#10b981", BLOCK: "#ef4444", REVIEW_REQUIRED: "#f59e0b", ERROR: "#a855f7" };

    if (activityTimeline.length === 0) {
        activityCard.innerHTML = `
            <h3 style="font-size:1.05rem;font-weight:700;margin-bottom:1rem;">Recent Review Activity</h3>
            <p style="color:var(--text-muted);font-size:0.9rem;text-align:center;padding:2rem 0;">No review activity recorded yet.</p>
        `;
    } else {
        activityCard.innerHTML = `
            <h3 style="font-size:1.05rem;font-weight:700;margin-bottom:1rem;">Recent Review Activity</h3>
            <div style="display:flex;flex-direction:column;gap:0.6rem;max-height:320px;overflow-y:auto;">
                ${activityTimeline.map(ev => {
                    const decision = (ev.detail || "PENDING").toUpperCase();
                    const color = decisionColor[decision] || "#9ca3af";
                    const ts = ev.timestamp ? new Date(ev.timestamp).toLocaleString() : "—";
                    return `
                        <div style="display:flex;align-items:center;justify-content:space-between;padding:0.6rem 0.75rem;background:rgba(255,255,255,0.03);border:1px solid var(--border-color);border-radius:var(--radius-sm);">
                            <div style="display:flex;align-items:center;gap:0.6rem;min-width:0;">
                                <div style="width:8px;height:8px;border-radius:50%;background:${color};flex-shrink:0;"></div>
                                <span style="font-size:0.85rem;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${dom.escape(ev.title || "—")}</span>
                            </div>
                            <div style="display:flex;align-items:center;gap:0.75rem;flex-shrink:0;">
                                <span style="font-size:0.75rem;color:${color};font-weight:600;">${dom.escape(decision)}</span>
                                <span style="font-size:0.72rem;color:var(--text-muted);">${dom.escape(ts)}</span>
                            </div>
                        </div>
                    `;
                }).join("")}
            </div>
        `;
    }

    container.append(metricsGrid, distGrid, leaderboardCard, trendCard, activityCard);
}

function _pct(val, total) {
    if (!total || total === 0) return 0;
    return Math.min(100, Math.round(((val || 0) / total) * 100));
}
