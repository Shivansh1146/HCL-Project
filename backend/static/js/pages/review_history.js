/**
 * pages/review_history.js — AI Review Dashboard & Review History.
 *
 * Feature 2.3 Visualization & Inspection Layer:
 *  - Statistics Cards: Total Reviews, SAFE, BLOCK, REVIEW_REQUIRED, ERROR, Avg Coverage %, Avg Processing Time, Total Comments Published
 *  - Visualizations: Decision Distribution, Severity Breakdown, Review Trend Timeline, Repository Comparison Leaderboard
 *  - Search & Filters: Repository, Author, Decision, Review Status, Date Range, Sort (Newest, Oldest, Highest Severity, Highest Coverage)
 *  - Review History Table: Paginated list with decision badges, status, GitHub review ID, coverage, processing time
 *  - Detail Drawer / Modal: Summary, Severity Cards, Complete AI Findings (File, Line, Severity, Category, Description, Suggestion, Comment Status), Developer Mode (Raw JSON viewer with 1-click copy)
 *  - Dark mode glassmorphism, responsive, loading skeletons, empty state, and error handling.
 */

import { api }             from "../services/api.js";
import { dom }             from "../utils/dom.js";
import { renderSkeleton }  from "../components/skeleton.js";
import { renderEmptyState } from "../components/empty_state.js";
import { Toast }           from "../components/toast.js";

let _state = {
    items: [],
    total: 0,
    page: 1,
    perPage: 20,
    totalPages: 1,
    stats: {
        total_reviews: 0,
        safe_count: 0,
        block_count: 0,
        review_required_count: 0,
        error_count: 0,
        avg_coverage: 100.0,
        avg_processing_time_sec: 3.8,
        total_comments_published: 0
    },
    analyticsData: null,
    filters: {
        searchQuery: "",
        repo: "all",
        author: "",
        decision: "all",
        review_status: "all",
        date_range: "all",
        sort: "newest"
    },
    isLoading: false,
    selectedPR: null
};

let _debounceTimer = null;
let _pollInterval = null;

function _startPolling() {
    _stopPolling();
    _pollInterval = setInterval(async () => {
        if (document.visibilityState !== "visible") return;
        try {
            await _loadDashboardData(true);
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
 * Main entry point for the Review History / AI Review Dashboard.
 * @param {HTMLElement} outlet
 */
export async function renderReviewHistoryPage(outlet) {
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
                AI Review Dashboard & History
            </h1>
            <p style="color:var(--text-secondary);font-size:0.95rem;">
                Inspect AI Review Decisions, Telemetry Metrics, Severity Distributions, and Findings
            </p>
        </div>
        <div style="display:flex;align-items:center;gap:0.75rem;">
            <button type="button" id="rh-refresh-btn" class="btn btn-secondary" style="gap:0.5rem;" aria-label="Refresh review history">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 11-.57-8.38l5.67-5.67"/></svg>
                Refresh
            </button>
            <button type="button" id="rh-export-csv-btn" class="btn btn-secondary" style="gap:0.5rem;" aria-label="Export CSV data">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
                Export CSV
            </button>
        </div>
    `;

    // Root containers
    const statsContainer = document.createElement("div");
    statsContainer.id = "rh-stats-container";

    const vizContainer = document.createElement("div");
    vizContainer.id = "rh-viz-container";

    const toolbarContainer = document.createElement("div");
    toolbarContainer.id = "rh-toolbar-container";

    const tableContainer = document.createElement("div");
    tableContainer.id = "rh-table-container";

    const drawerMount = document.createElement("div");
    drawerMount.id = "rh-drawer-mount";

    wrapper.append(header, statsContainer, vizContainer, toolbarContainer, tableContainer, drawerMount);
    outlet.appendChild(wrapper);

    // Event listeners
    header.querySelector("#rh-refresh-btn")?.addEventListener("click", async () => {
        await _loadDashboardData();
        Toast.success("Review history data refreshed.");
    });
    header.querySelector("#rh-export-csv-btn")?.addEventListener("click", () => {
        api.exportAnalytics("csv");
    });

    // Fetch data
    await _loadDashboardData();

    window.addEventListener("router:before-navigate", _stopPolling, { once: true });
    _startPolling();
}

async function _loadDashboardData(silent = false) {
    if (!silent) {
        _state.isLoading = true;
        _renderSkeletonState();
    }

    try {
        const [prRes, statsRes, analyticsRes] = await Promise.allSettled([
            api.getPullRequests({
                page: _state.page,
                per_page: _state.perPage,
                repo: _state.filters.repo !== "all" ? _state.filters.repo : undefined,
                author: _state.filters.author || undefined,
                decision: _state.filters.decision !== "all" ? _state.filters.decision : undefined,
                review_status: _state.filters.review_status !== "all" ? _state.filters.review_status : undefined,
                sort: _state.filters.sort,
                date_range: _state.filters.date_range !== "all" ? _state.filters.date_range : undefined,
                q: _state.filters.searchQuery || undefined
            }),
            api.getPullRequestStats(),
            api.getAnalytics()
        ]);

        if (prRes.status === "fulfilled" && prRes.value) {
            _state.items = prRes.value.items || [];
            _state.total = prRes.value.total || 0;
            _state.totalPages = prRes.value.total_pages || 1;
        } else {
            _state.items = [];
            _state.total = 0;
        }

        if (statsRes.status === "fulfilled" && statsRes.value) {
            _state.stats = { ..._state.stats, ...statsRes.value };
        }

        if (analyticsRes.status === "fulfilled" && analyticsRes.value) {
            _state.analyticsData = analyticsRes.value;
        }
    } catch (err) {
        console.error("[ReviewHistory] Error fetching dashboard data:", err);
        Toast.error("Failed to load AI review history.");
    } finally {
        if (!silent) {
            _state.isLoading = false;
        }
        _renderStatsCards();
        _renderVisualizations();
        _renderToolbar();
        _renderTable();
    }
}

function _renderSkeletonState() {
    const tableContainer = document.getElementById("rh-table-container");
    if (tableContainer) {
        tableContainer.innerHTML = `
            <div style="display:flex;flex-direction:column;gap:1rem;">
                ${renderSkeleton("table")}
            </div>
        `;
    }
}

function _renderStatsCards() {
    const container = document.getElementById("rh-stats-container");
    if (!container) return;

    const s = _state.stats;
    // Use the backend's total_reviews directly from /api/prs/stats
    // This counts PRs with review_status IN ('success', 'failed', 'processing')
    const totalRev = s.total_reviews || 0;
    // Use the backend's decision counts directly
    const safeCount = s.safe_count || 0;
    const blockCount = s.block_count || 0;
    const reviewRequiredCount = s.review_required_count || 0;
    const errorCount = s.error_count || 0;

    container.innerHTML = `
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:1rem;margin-bottom:1.5rem;">
            <div class="glass-card" style="padding:1.1rem 1.25rem;">
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">Total AI Reviews</span>
                <strong style="font-size:1.6rem;font-weight:800;color:var(--primary);">${totalRev}</strong>
                <p style="font-size:0.7rem;color:var(--text-muted);margin-top:0.2rem;">Processed PR Analyses</p>
            </div>
            <div class="glass-card" style="padding:1.1rem 1.25rem;">
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">SAFE / Approved</span>
                <strong style="font-size:1.6rem;font-weight:800;color:var(--color-success);">${safeCount}</strong>
                <p style="font-size:0.7rem;color:var(--text-muted);margin-top:0.2rem;">Low / Code Smell Codebases</p>
            </div>
            <div class="glass-card" style="padding:1.1rem 1.25rem;">
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">REVIEW REQUIRED</span>
                <strong style="font-size:1.6rem;font-weight:800;color:var(--severity-medium);">${reviewRequiredCount}</strong>
                <p style="font-size:0.7rem;color:var(--text-muted);margin-top:0.2rem;">Needs Human Inspection</p>
            </div>
            <div class="glass-card" style="padding:1.1rem 1.25rem;">
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">BLOCKED / High / Critical</span>
                <strong style="font-size:1.6rem;font-weight:800;color:var(--severity-high);">${blockCount}</strong>
                <p style="font-size:0.7rem;color:var(--text-muted);margin-top:0.2rem;">Critical Issues Found</p>
            </div>
            <div class="glass-card" style="padding:1.1rem 1.25rem;">
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">ERROR / Failed</span>
                <strong style="font-size:1.6rem;font-weight:800;color:#a855f7;">${errorCount}</strong>
                <p style="font-size:0.7rem;color:var(--text-muted);margin-top:0.2rem;">Execution Failures</p>
            </div>
            <div class="glass-card" style="padding:1.1rem 1.25rem;">
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">Average Coverage</span>
                <strong style="font-size:1.6rem;font-weight:800;color:var(--color-info);">${s.avg_coverage || 100.0}%</strong>
                <p style="font-size:0.7rem;color:var(--text-muted);margin-top:0.2rem;">Analyzed Chunks Ratio</p>
            </div>
            <div class="glass-card" style="padding:1.1rem 1.25rem;">
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">Avg Processing Time</span>
                <strong style="font-size:1.6rem;font-weight:800;color:var(--text-primary);">${s.avg_processing_time_sec || 3.8}s</strong>
                <p style="font-size:0.7rem;color:var(--text-muted);margin-top:0.2rem;">Latency Per Pull Request</p>
            </div>
            <div class="glass-card" style="padding:1.1rem 1.25rem;">
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">Published Reviews</span>
                <strong style="font-size:1.6rem;font-weight:800;color:var(--color-success);">${s.total_comments_published || 0}</strong>
                <p style="font-size:0.7rem;color:var(--text-muted);margin-top:0.2rem;">Posted to GitHub PRs</p>
            </div>
        </div>
    `;
}

function _renderVisualizations() {
    const container = document.getElementById("rh-viz-container");
    if (!container) return;

    const ad = _state.analyticsData || {};
    const dec = ad.decision_distribution || {
        SAFE: _state.stats.safe_count || 0,
        REVIEW_REQUIRED: _state.stats.review_required_count || 0,
        BLOCK: _state.stats.block_count || 0,
        ERROR: _state.stats.error_count || 0
    };
    const sev = ad.severity_distribution || { high: 0, medium: 0, low: 0 };
    const repos = ad.repository_analytics || [];
    const trends = ad.daily_trends || [];

    const totalDecisions = (dec.SAFE || 0) + (dec.REVIEW_REQUIRED || 0) + (dec.BLOCK || 0) + (dec.ERROR || 0) || 1;
    const totalSeverities = (sev.high || 0) + (sev.medium || 0) + (sev.low || 0) || 1;

    container.innerHTML = `
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(320px, 1fr));gap:1.5rem;margin-bottom:1.5rem;">
            <!-- Chart 1: Decision Distribution -->
            <div class="glass-card" style="padding:1.25rem;">
                <h3 style="font-size:1rem;font-weight:700;margin-bottom:1rem;display:flex;align-items:center;justify-content:space-between;">
                    <span>Decision Distribution</span>
                    <span style="font-size:0.75rem;color:var(--text-muted);">${totalDecisions} Reviews</span>
                </h3>
                <div style="display:flex;height:12px;border-radius:6px;overflow:hidden;background:rgba(255,255,255,0.05);margin-bottom:1rem;">
                    <div style="width:${_pct(dec.SAFE, totalDecisions)}%;background:var(--color-success);" title="SAFE: ${dec.SAFE || 0}"></div>
                    <div style="width:${_pct(dec.REVIEW_REQUIRED, totalDecisions)}%;background:var(--severity-medium);" title="REVIEW REQUIRED: ${dec.REVIEW_REQUIRED || 0}"></div>
                    <div style="width:${_pct(dec.BLOCK, totalDecisions)}%;background:var(--severity-high);" title="BLOCK: ${dec.BLOCK || 0}"></div>
                    <div style="width:${_pct(dec.ERROR, totalDecisions)}%;background:#a855f7;" title="ERROR: ${dec.ERROR || 0}"></div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;font-size:0.8rem;">
                    <div style="display:flex;align-items:center;gap:0.4rem;">
                        <span style="width:8px;height:8px;border-radius:50%;background:var(--color-success);"></span>
                        <span>SAFE: <strong>${dec.SAFE || 0}</strong> (${_pct(dec.SAFE, totalDecisions)}%)</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:0.4rem;">
                        <span style="width:8px;height:8px;border-radius:50%;background:var(--severity-medium);"></span>
                        <span>REVIEW REQ: <strong>${dec.REVIEW_REQUIRED || 0}</strong> (${_pct(dec.REVIEW_REQUIRED, totalDecisions)}%)</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:0.4rem;">
                        <span style="width:8px;height:8px;border-radius:50%;background:var(--severity-high);"></span>
                        <span>BLOCK: <strong>${dec.BLOCK || 0}</strong> (${_pct(dec.BLOCK, totalDecisions)}%)</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:0.4rem;">
                        <span style="width:8px;height:8px;border-radius:50%;background:#a855f7;"></span>
                        <span>ERROR: <strong>${dec.ERROR || 0}</strong> (${_pct(dec.ERROR, totalDecisions)}%)</span>
                    </div>
                </div>
            </div>

            <!-- Chart 2: Severity Distribution -->
            <div class="glass-card" style="padding:1.25rem;">
                <h3 style="font-size:1rem;font-weight:700;margin-bottom:1rem;display:flex;align-items:center;justify-content:space-between;">
                    <span>Severity Distribution</span>
                    <span style="font-size:0.75rem;color:var(--text-muted);">${(sev.high||0)+(sev.medium||0)+(sev.low||0)} Issues</span>
                </h3>
                <div style="display:flex;height:12px;border-radius:6px;overflow:hidden;background:rgba(255,255,255,0.05);margin-bottom:1rem;">
                    <div style="width:${_pct(sev.high, totalSeverities)}%;background:var(--severity-high);" title="High: ${sev.high || 0}"></div>
                    <div style="width:${_pct(sev.medium, totalSeverities)}%;background:var(--severity-medium);" title="Medium: ${sev.medium || 0}"></div>
                    <div style="width:${_pct(sev.low, totalSeverities)}%;background:var(--severity-low);" title="Low: ${sev.low || 0}"></div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.5rem;font-size:0.8rem;">
                    <div style="display:flex;align-items:center;gap:0.4rem;">
                        <span style="width:8px;height:8px;border-radius:50%;background:var(--severity-high);"></span>
                        <span>High / Critical: <strong>${sev.high || 0}</strong></span>
                    </div>
                    <div style="display:flex;align-items:center;gap:0.4rem;">
                        <span style="width:8px;height:8px;border-radius:50%;background:var(--severity-medium);"></span>
                        <span>Medium: <strong>${sev.medium || 0}</strong></span>
                    </div>
                    <div style="display:flex;align-items:center;gap:0.4rem;">
                        <span style="width:8px;height:8px;border-radius:50%;background:var(--severity-low);"></span>
                        <span>Low / Code Smell: <strong>${sev.low || 0}</strong></span>
                    </div>
                </div>
            </div>

            <!-- Chart 3: Review Trend Activity -->
            <div class="glass-card" style="padding:1.25rem;">
                <h3 style="font-size:1rem;font-weight:700;margin-bottom:0.75rem;">Review Trend Activity</h3>
                <div style="display:flex;align-items:flex-end;gap:0.35rem;height:65px;padding-top:0.5rem;">
                    ${trends.length > 0 ? trends.map(t => {
                        const maxVal = Math.max(...trends.map(x => x.count), 1);
                        const heightPct = Math.max(15, Math.round((t.count / maxVal) * 100));
                        return `
                            <div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;gap:0.25rem;" title="${t.date}: ${t.count} reviews">
                                <div style="width:100%;height:${heightPct}%;background:linear-gradient(180deg,#3b82f6,#8b5cf6);border-radius:3px 3px 0 0;"></div>
                            </div>
                        `;
                    }).join("") : `<div style="color:var(--text-muted);font-size:0.8rem;text-align:center;width:100%;">No daily activity recorded yet.</div>`}
                </div>
                <div style="display:flex;justify-content:space-between;font-size:0.7rem;color:var(--text-muted);margin-top:0.5rem;">
                    <span>${trends[0]?.date || "14d ago"}</span>
                    <span>${trends[trends.length - 1]?.date || "Today"}</span>
                </div>
            </div>
        </div>
    `;
}

function _renderToolbar() {
    const container = document.getElementById("rh-toolbar-container");
    if (!container) return;

    container.innerHTML = "";
    const card = document.createElement("div");
    card.className = "glass-card";
    card.style.cssText = "margin-bottom:1.5rem;padding:1rem 1.25rem;display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap;";

    // Search bar
    const searchWrap = document.createElement("div");
    searchWrap.style.cssText = "flex:1;min-width:220px;position:relative;";
    searchWrap.innerHTML = `
        <input type="text" id="rh-search-input" class="form-input" placeholder="Search by title, repo, or author…"
               value="${dom.escape(_state.filters.searchQuery)}" aria-label="Search review history" style="padding-left:2.4rem;">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="position:absolute;left:0.85rem;top:50%;transform:translateY(-50%);color:var(--text-muted);"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    `;
    const searchInput = searchWrap.querySelector("#rh-search-input");
    searchInput.addEventListener("input", (e) => {
        clearTimeout(_debounceTimer);
        _debounceTimer = setTimeout(async () => {
            _state.filters.searchQuery = e.target.value;
            _state.page = 1;
            await _loadDashboardData();
        }, 250);
    });

    // Decision Filter
    const decSelect = document.createElement("select");
    decSelect.className = "form-select";
    decSelect.setAttribute("aria-label", "Filter by Decision");
    decSelect.style.cssText = "width:auto;min-width:140px;";
    decSelect.innerHTML = `
        <option value="all" ${_state.filters.decision === "all" ? "selected" : ""}>All Decisions</option>
        <option value="SAFE" ${_state.filters.decision === "SAFE" ? "selected" : ""}>✅ SAFE</option>
        <option value="REVIEW_REQUIRED" ${_state.filters.decision === "REVIEW_REQUIRED" ? "selected" : ""}>⚠️ REVIEW REQUIRED</option>
        <option value="BLOCK" ${_state.filters.decision === "BLOCK" ? "selected" : ""}>🚨 BLOCK</option>
        <option value="ERROR" ${_state.filters.decision === "ERROR" ? "selected" : ""}>💥 ERROR</option>
    `;
    decSelect.addEventListener("change", async (e) => {
        _state.filters.decision = e.target.value;
        _state.page = 1;
        await _loadDashboardData();
    });

    // Review Status Filter
    const statusSelect = document.createElement("select");
    statusSelect.className = "form-select";
    statusSelect.setAttribute("aria-label", "Filter by Review Status");
    statusSelect.style.cssText = "width:auto;min-width:140px;";
    statusSelect.innerHTML = `
        <option value="all" ${_state.filters.review_status === "all" ? "selected" : ""}>All Statuses</option>
        <option value="success" ${_state.filters.review_status === "success" ? "selected" : ""}>Completed</option>
        <option value="pending" ${_state.filters.review_status === "pending" ? "selected" : ""}>Pending</option>
        <option value="processing" ${_state.filters.review_status === "processing" ? "selected" : ""}>Processing</option>
        <option value="failed" ${_state.filters.review_status === "failed" ? "selected" : ""}>Failed</option>
    `;
    statusSelect.addEventListener("change", async (e) => {
        _state.filters.review_status = e.target.value;
        _state.page = 1;
        await _loadDashboardData();
    });

    // Date Range Filter
    const dateSelect = document.createElement("select");
    dateSelect.className = "form-select";
    dateSelect.setAttribute("aria-label", "Filter by Date Range");
    dateSelect.style.cssText = "width:auto;min-width:120px;";
    dateSelect.innerHTML = `
        <option value="all" ${_state.filters.date_range === "all" ? "selected" : ""}>All Time</option>
        <option value="7d" ${_state.filters.date_range === "7d" ? "selected" : ""}>Last 7 Days</option>
        <option value="30d" ${_state.filters.date_range === "30d" ? "selected" : ""}>Last 30 Days</option>
        <option value="90d" ${_state.filters.date_range === "90d" ? "selected" : ""}>Last 90 Days</option>
    `;
    dateSelect.addEventListener("change", async (e) => {
        _state.filters.date_range = e.target.value;
        _state.page = 1;
        await _loadDashboardData();
    });

    // Sort Dropdown
    const sortSelect = document.createElement("select");
    sortSelect.className = "form-select";
    sortSelect.setAttribute("aria-label", "Sort Reviews");
    sortSelect.style.cssText = "width:auto;min-width:140px;";
    sortSelect.innerHTML = `
        <option value="newest" ${_state.filters.sort === "newest" ? "selected" : ""}>Sort: Newest</option>
        <option value="oldest" ${_state.filters.sort === "oldest" ? "selected" : ""}>Sort: Oldest</option>
        <option value="highest_severity" ${_state.filters.sort === "highest_severity" ? "selected" : ""}>Sort: Highest Severity</option>
        <option value="highest_coverage" ${_state.filters.sort === "highest_coverage" ? "selected" : ""}>Sort: Highest Coverage</option>
    `;
    sortSelect.addEventListener("change", async (e) => {
        _state.filters.sort = e.target.value;
        _state.page = 1;
        await _loadDashboardData();
    });

    card.append(searchWrap, decSelect, statusSelect, dateSelect, sortSelect);
    container.appendChild(card);
}

function _renderTable() {
    const container = document.getElementById("rh-table-container");
    if (!container) return;

    container.innerHTML = "";
    const items = _state.items;

    if (items.length === 0) {
        renderEmptyState(container, {
            title: "No AI Reviews Found",
            description: _state.filters.searchQuery
                ? `No reviews match query "${dom.escape(_state.filters.searchQuery)}".`
                : "No AI code reviews found in database. Ingest pull request events to automatically trigger reviews.",
            icon: `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>`
        });
        return;
    }

    const tableCard = document.createElement("div");
    tableCard.className = "glass-card";
    tableCard.style.cssText = "overflow-x:auto;";

    const table = document.createElement("table");
    table.style.cssText = "width:100%;border-collapse:collapse;text-align:left;font-size:0.88rem;";

    table.innerHTML = `
        <thead>
            <tr style="border-bottom:1px solid var(--border-color);color:var(--text-muted);font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;white-space:nowrap;">
                <th style="padding:0.7rem 0.6rem;">Repository</th>
                <th style="padding:0.7rem 0.6rem;">PR #</th>
                <th style="padding:0.7rem 0.6rem;width:100%;">PR Title</th>
                <th style="padding:0.7rem 0.6rem;">Author</th>
                <th style="padding:0.7rem 0.6rem;">AI Decision</th>
                <th style="padding:0.7rem 0.6rem;">Review Status</th>
                <th style="padding:0.7rem 0.6rem;">Published</th>
                <th style="padding:0.7rem 0.6rem;">Coverage</th>
                <th style="padding:0.7rem 0.6rem;">Latency</th>
                <th style="padding:0.7rem 0.6rem;">Timestamp</th>
                <th style="padding:0.7rem 0.6rem;">Actions</th>
            </tr>
        </thead>
        <tbody style="white-space:nowrap;">
            ${items.map(pr => {
                const repoName = dom.escape(pr.repository_name || `${pr.owner}/${pr.repository_name}`);
                const title = dom.escape(pr.title || "Untitled Pull Request");
                const author = dom.escape(pr.author_login || "unknown");
                const prUrl = pr.html_url ? dom.escape(pr.html_url) : "#";
                const decisionBadge = _getDecisionBadge(pr);
                const statusBadge = _getStatusBadge(pr);
                const publishedBadge = _getPublishedBadge(pr);
                const coveragePct = `${pr.coverage_percentage || 100.0}%`;
                const procTime = `${pr.processing_time_sec || 3.8}s`;
                const timestamp = dom.escape(new Date(pr.reviewed_at || pr.updated_at || Date.now()).toLocaleString());
                const owner = dom.escape(pr.owner || (pr.repository_name || "").split("/")[0] || "");
                const repoOnly = dom.escape((pr.repository_name || "").split("/").pop() || pr.repository_name);

                return `
                    <tr style="border-bottom:1px solid var(--border-color);transition:background 0.2s;" class="table-row-hover">
                        <td style="padding:0.6rem;font-weight:600;color:var(--text-primary);">${repoName}</td>
                        <td style="padding:0.6rem;">
                            <a href="${prUrl}" target="_blank" rel="noopener noreferrer" style="color:var(--primary);font-weight:700;text-decoration:none;">
                                #${pr.number}
                            </a>
                        </td>
                        <td style="padding:0.6rem;max-width:200px;overflow:hidden;text-overflow:ellipsis;" title="${title}">
                            ${title}
                        </td>
                        <td style="padding:0.6rem;color:var(--text-secondary);">
                            <div style="display:flex;align-items:center;gap:0.4rem;">
                                ${pr.author_avatar ? `<img src="${dom.escape(pr.author_avatar)}" alt="${author}" style="width:20px;height:20px;border-radius:50%;">` : ""}
                                <span>${author}</span>
                            </div>
                        </td>
                        <td style="padding:0.6rem;">${decisionBadge}</td>
                        <td style="padding:0.6rem;">${statusBadge}</td>
                        <td style="padding:0.6rem;">${publishedBadge}</td>
                        <td style="padding:0.6rem;font-weight:600;color:var(--color-info);">${coveragePct}</td>
                        <td style="padding:0.6rem;color:var(--text-muted);">${procTime}</td>
                        <td style="padding:0.6rem;color:var(--text-muted);font-size:0.75rem;">${timestamp}</td>
                        <td style="padding:0.6rem;">
                            <div style="display:flex;align-items:center;gap:0.4rem;">
                                <button
                                    type="button"
                                    class="btn btn-secondary"
                                    style="font-size:0.75rem;padding:0.25rem 0.6rem;"
                                    id="inspect-btn-${pr.id}"
                                    data-pr-id="${pr.id}"
                                    data-owner="${owner}"
                                    data-repo="${repoOnly}"
                                    data-pr-number="${pr.number}"
                                    aria-label="Inspect AI Review details for PR #${pr.number}"
                                >
                                    🔍 Inspect
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
            }).join("")}
        </tbody>
    `;

    // Attach button click listeners
    table.querySelectorAll("[id^='inspect-btn-']").forEach(btn => {
        btn.addEventListener("click", async () => {
            const { owner, repo, prNumber } = btn.dataset;
            await _openReviewDetailDrawer(owner, repo, parseInt(prNumber, 10));
        });
    });

    tableCard.appendChild(table);
    container.appendChild(tableCard);
}

function _getDecisionBadge(pr) {
    const decision = (pr.decision || "PENDING").toUpperCase();
    const badges = {
        "SAFE": `<span class="badge badge-success">✅ SAFE</span>`,
        "PERFECT": `<span class="badge badge-success">🌟 PERFECT</span>`,
        "REVIEW_REQUIRED": `<span class="badge badge-warning">⚠️ REVIEW REQUIRED</span>`,
        "BLOCK": `<span class="badge badge-error">🚨 BLOCK</span>`,
        "ERROR": `<span class="badge badge-purple" style="background:rgba(168,85,247,0.15);color:#c084fc;border:1px solid rgba(168,85,247,0.3);">💥 ERROR</span>`
    };
    return badges[decision] || `<span class="badge badge-muted">⏳ PENDING</span>`;
}

function _getStatusBadge(pr) {
    const status = (pr.review_status || "pending").toLowerCase();
    const map = {
        "success": `<span style="color:#10b981;font-weight:600;font-size:0.78rem;">Completed</span>`,
        "pending": `<span style="color:#9ca3af;font-size:0.78rem;">Pending</span>`,
        "processing": `<span style="color:#3b82f6;font-weight:600;font-size:0.78rem;">Processing</span>`,
        "failed": `<span style="color:#ef4444;font-weight:600;font-size:0.78rem;">Failed</span>`
    };
    return map[status] || `<span style="color:var(--text-muted);font-size:0.78rem;">${status}</span>`;
}

function _getPublishedBadge(pr) {
    if (pr.review_posted) {
        const reviewId = pr.github_review_id ? `#${pr.github_review_id}` : "";
        return `<span class="badge badge-success" style="font-size:0.7rem;">✅ Published ${reviewId}</span>`;
    }
    if (pr.review_status === "success") {
        return `<span class="badge badge-muted" style="font-size:0.7rem;">Not Published</span>`;
    }
    return `<span style="color:var(--text-muted);font-size:0.78rem;">—</span>`;
}

async function _openReviewDetailDrawer(owner, repo, prNumber) {
    const mount = document.getElementById("rh-drawer-mount");
    if (!mount) return;

    mount.innerHTML = `
        <div style="position:fixed;inset:0;background:rgba(0,0,0,0.6);backdrop-filter:blur(4px);z-index:999;display:flex;justify-content:flex-end;" id="rh-modal-overlay">
            <div style="width:100%;max-width:720px;height:100vh;background:var(--bg-card,#0f172a);border-left:1px solid var(--border-color);padding:1.5rem;overflow-y:auto;box-shadow:-10px 0 30px rgba(0,0,0,0.5);" class="animate-fade-in" id="rh-drawer-content">
                <div style="display:flex;align-items:center;justify-content:center;height:50vh;">
                    <div class="spinner" aria-label="Loading review details"></div>
                </div>
            </div>
        </div>
    `;

    const overlay = mount.querySelector("#rh-modal-overlay");
    const drawerContent = mount.querySelector("#rh-drawer-content");

    overlay.addEventListener("click", (e) => {
        if (e.target === overlay) mount.innerHTML = "";
    });

    try {
        const details = await api.getPullRequestDetail(owner, repo, prNumber);
        _renderDrawerDetails(drawerContent, details, mount);
    } catch (err) {
        console.error("[ReviewHistory] Error opening drawer:", err);
        Toast.error("Failed to load review details.");
        mount.innerHTML = "";
    }
}

function _renderDrawerDetails(container, details, mount) {
    const pr = details || {};
    const title = dom.escape(pr.title || "Pull Request Details");
    const repo = dom.escape(pr.repo || pr.repository_name || "");
    const prNumber = pr.pr_number || pr.number;
    const author = dom.escape(pr.author_login || "author");
    const summary = pr.review_summary || "No automated review summary recorded.";
    const issues = Array.isArray(pr.issues) ? pr.issues : (typeof pr.issues_json === "string" ? JSON.parse(pr.issues_json || "[]") : []);
    
    let prevIssues = null;
    try {
        prevIssues = pr.previous_issues_json ? JSON.parse(pr.previous_issues_json) : null;
    } catch (e) {
        prevIssues = null;
    }

    let viewMode = 'insights'; // 'insights', 'comparison', 'dev'

    // Compute derived metrics
    const filesReviewed = new Set(issues.map(i => i.file_path || i.file)).size || 1; 
    const coverage = pr.coverage_percentage || 100.0;
    const confidence = Math.max(50, Math.round(coverage - ((pr.high_count || 0) * 2) - ((pr.medium_count || 0) * 0.5)));
    const riskScore = Math.min(100, Math.round(((pr.high_count || 0) * 10) + ((pr.medium_count || 0) * 3) + ((pr.low_count || 0) * 1)));
    
    // Category aggregation
    const categories = issues.reduce((acc, iss) => {
        const cat = (iss.category || iss.type || "other").toLowerCase();
        acc[cat] = (acc[cat] || 0) + 1;
        return acc;
    }, {});

    // Pseudo-scores for Summary Section
    const secIssues = categories.security || 0;
    const perfIssues = categories.performance || 0;
    const maintIssues = (categories.maintainability || 0) + (categories.code_quality || 0);
    const relIssues = categories.reliability || categories.bug || 0;

    const securityScore = Math.max(0, 100 - (secIssues * 20));
    const perfScore = Math.max(0, 100 - (perfIssues * 15));
    const maintScore = Math.max(0, 100 - (maintIssues * 10));
    const relScore = Math.max(0, 100 - (relIssues * 15));
    const overallQuality = Math.round((securityScore + perfScore + maintScore + relScore) / 4);

    function buildDrawerHTML() {
        return `
            <!-- Drawer Header -->
            <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:1.25rem;border-bottom:1px solid var(--border-color);padding-bottom:1rem;">
                <div>
                    <span style="font-size:0.8rem;color:var(--primary);font-weight:700;">${repo} #${prNumber}</span>
                    <h2 style="font-size:1.3rem;font-weight:800;letter-spacing:-0.02em;margin:0.2rem 0;">${title}</h2>
                    <p style="font-size:0.8rem;color:var(--text-muted);">Submitted by @${author} • Reviewed at ${dom.escape(new Date(pr.reviewed_at || Date.now()).toLocaleString())}</p>
                    <p style="font-size:0.75rem;color:var(--text-secondary);margin-top:0.25rem;">Model Used: <span class="badge badge-info" style="font-size:0.65rem;">Groq / Llama3 8B</span> • Review Duration: ${pr.processing_time_sec || 3.8}s • Files Analyzed: ${Math.max(1, filesReviewed)}</p>
                </div>
                <button type="button" class="icon-btn" id="close-drawer-btn" style="font-size:1.2rem;width:32px;height:32px;" aria-label="Close detail drawer">✕</button>
            </div>

            <!-- View Mode Switcher -->
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.25rem;">
                <div style="display:flex;gap:0.5rem;background:rgba(255,255,255,0.04);padding:0.25rem;border-radius:var(--radius-md);">
                    <button type="button" id="tab-insights-btn" class="btn ${viewMode === 'insights' ? 'btn-primary' : 'btn-ghost'}" style="font-size:0.78rem;padding:0.3rem 0.8rem;">
                        AI Insights
                    </button>
                    ${prevIssues ? `
                    <button type="button" id="tab-comparison-btn" class="btn ${viewMode === 'comparison' ? 'btn-primary' : 'btn-ghost'}" style="font-size:0.78rem;padding:0.3rem 0.8rem;">
                        Compare History
                    </button>
                    ` : ''}
                    <button type="button" id="tab-devmode-btn" class="btn ${viewMode === 'dev' ? 'btn-primary' : 'btn-ghost'}" style="font-size:0.78rem;padding:0.3rem 0.8rem;">
                        Raw JSON
                    </button>
                </div>
                ${pr.review_posted ? `<span class="badge badge-success">✅ GitHub Review #${pr.github_review_id || ""} Published</span>` : `<span class="badge badge-muted">Unpublished Review</span>`}
            </div>

            ${viewMode === 'insights' ? `
                <!-- Visualization & KPI Cards -->
                <div style="display:grid;grid-template-columns:repeat(5, 1fr);gap:0.75rem;margin-bottom:1.25rem;">
                    <div class="glass-card" style="padding:0.75rem;text-align:center;">
                        <span style="font-size:0.7rem;color:var(--text-muted);display:block;">Confidence Level</span>
                        <div style="margin-top:0.5rem;height:6px;background:var(--border-color);border-radius:3px;overflow:hidden;">
                            <div style="width:${confidence}%;height:100%;background:${confidence > 80 ? 'var(--color-success)' : 'var(--color-warning)'};"></div>
                        </div>
                        <strong style="font-size:0.95rem;color:var(--text-primary);display:block;margin-top:0.25rem;">${confidence}%</strong>
                    </div>
                    <div class="glass-card" style="padding:0.75rem;text-align:center;">
                        <span style="font-size:0.7rem;color:var(--text-muted);display:block;">Coverage</span>
                        <div style="margin-top:0.5rem;height:6px;background:var(--border-color);border-radius:3px;overflow:hidden;">
                            <div style="width:${coverage}%;height:100%;background:var(--severity-low);"></div>
                        </div>
                        <strong style="font-size:0.95rem;color:var(--text-primary);display:block;margin-top:0.25rem;">${coverage}%</strong>
                    </div>
                    <div class="glass-card" style="padding:0.75rem;text-align:center;">
                        <span style="font-size:0.7rem;color:var(--text-muted);display:block;">Decision</span>
                        <strong style="font-size:0.95rem;color:var(--text-primary);display:block;margin-top:0.5rem;">${pr.decision || "SAFE"}</strong>
                    </div>
                    <div class="glass-card" style="padding:0.75rem;text-align:center;">
                        <span style="font-size:0.7rem;color:var(--text-muted);display:block;">Risk Score</span>
                        <strong style="font-size:1.2rem;color:${riskScore > 50 ? 'var(--severity-high)' : riskScore > 20 ? 'var(--severity-medium)' : 'var(--color-success)'};display:block;margin-top:0.25rem;">${riskScore}</strong>
                    </div>
                    <div class="glass-card" style="padding:0.75rem;text-align:center;">
                        <span style="font-size:0.7rem;color:var(--text-muted);display:block;">Issues</span>
                        <div style="display:flex;justify-content:center;gap:0.25rem;margin-top:0.5rem;font-size:0.7rem;">
                            <span style="color:var(--severity-high);" title="High Risk">H:${pr.high_count || 0}</span>
                            <span style="color:var(--severity-medium);" title="Medium Risk">M:${pr.medium_count || 0}</span>
                            <span style="color:var(--severity-low);" title="Low Risk">L:${pr.low_count || 0}</span>
                        </div>
                    </div>
                </div>

                <!-- Summary Section -->
                <div class="glass-card" style="padding:1rem;margin-bottom:1.25rem;">
                    <h4 style="font-size:0.85rem;font-weight:700;color:var(--text-secondary);margin-bottom:0.75rem;text-transform:uppercase;letter-spacing:0.04em;">Code Quality Summary</h4>
                    <div style="display:grid;grid-template-columns:repeat(5, 1fr);gap:1rem;text-align:center;margin-bottom:1rem;border-bottom:1px solid var(--border-color);padding-bottom:1rem;">
                        <div><span style="font-size:0.7rem;color:var(--text-muted);">Overall</span><br><strong style="color:${overallQuality > 80 ? 'var(--color-success)' : 'var(--color-warning)'};">${overallQuality}/100</strong></div>
                        <div><span style="font-size:0.7rem;color:var(--text-muted);">Security</span><br><strong style="color:${securityScore > 80 ? 'var(--color-success)' : 'var(--color-warning)'};">${securityScore}/100</strong></div>
                        <div><span style="font-size:0.7rem;color:var(--text-muted);">Performance</span><br><strong style="color:${perfScore > 80 ? 'var(--color-success)' : 'var(--color-warning)'};">${perfScore}/100</strong></div>
                        <div><span style="font-size:0.7rem;color:var(--text-muted);">Maintainability</span><br><strong style="color:${maintScore > 80 ? 'var(--color-success)' : 'var(--color-warning)'};">${maintScore}/100</strong></div>
                        <div><span style="font-size:0.7rem;color:var(--text-muted);">Reliability</span><br><strong style="color:${relScore > 80 ? 'var(--color-success)' : 'var(--color-warning)'};">${relScore}/100</strong></div>
                    </div>
                    <div style="font-size:0.85rem;line-height:1.5;color:var(--text-primary);white-space:pre-wrap;">${dom.escape(summary)}</div>
                </div>

                <!-- Detailed Findings with Explainability -->
                <div class="glass-card" style="padding:1rem;">
                    <h4 style="font-size:0.85rem;font-weight:700;color:var(--text-secondary);margin-bottom:0.75rem;text-transform:uppercase;letter-spacing:0.04em;">AI Explanations & Findings (${issues.length})</h4>
                    ${issues.length > 0 ? `
                        <div style="display:flex;flex-direction:column;gap:1rem;">
                            ${issues.map((iss, idx) => {
                                const file = dom.escape(iss.file_path || iss.file || "N/A");
                                const line = iss.line_number ?? iss.line ?? 0;
                                const sev = (iss.severity || "low").toLowerCase();
                                const cat = dom.escape(iss.category || iss.type || "code_quality");
                                const title = dom.escape(iss.title || iss.description || "Issue Detected");
                                const desc = dom.escape(iss.description || "");
                                const fix = dom.escape(iss.suggestion || iss.fix || "No specific fix provided.");
                                
                                return `
                                    <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border-color);border-radius:var(--radius-md);padding:1rem;">
                                        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.5rem;">
                                            <div style="font-weight:600;color:var(--text-primary);">${title}</div>
                                            <span class="badge ${sev === 'high' ? 'badge-severity-high' : sev === 'medium' ? 'badge-severity-medium' : 'badge-severity-low'}" style="font-size:0.65rem;">${sev.toUpperCase()} RISK</span>
                                        </div>
                                        <div style="font-family:monospace;font-size:0.75rem;color:var(--primary);margin-bottom:0.75rem;background:rgba(0,0,0,0.2);padding:0.25rem 0.5rem;border-radius:4px;display:inline-block;">
                                            ${file}:${line > 0 ? line : '*'}
                                        </div>
                                        <div style="display:grid;grid-template-columns:1fr;gap:0.75rem;font-size:0.8rem;color:var(--text-secondary);">
                                            <div><strong style="color:var(--text-primary);">Why AI flagged it:</strong> ${desc}</div>
                                            <div><strong style="color:var(--text-primary);">Potential Impact:</strong> This issue negatively impacts the <em>${cat}</em> and overall quality of the codebase.</div>
                                            <div style="background:rgba(16,185,129,0.05);padding:0.5rem;border-left:3px solid var(--color-success);border-radius:0 4px 4px 0;"><strong style="color:var(--color-success);">Suggested Improvement:</strong> ${fix}</div>
                                        </div>
                                    </div>
                                `;
                            }).join("")}
                        </div>
                    ` : `<p style="font-size:0.85rem;color:var(--text-muted);">No issues detected by AI analysis. Code structure is clean.</p>`}
                </div>
            ` : viewMode === 'comparison' ? `
                <!-- Comparison View -->
                <div class="glass-card" style="padding:1rem;">
                    <h4 style="font-size:0.85rem;font-weight:700;color:var(--text-secondary);margin-bottom:0.75rem;text-transform:uppercase;letter-spacing:0.04em;">Review Comparison</h4>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
                        <div style="background:rgba(255,255,255,0.02);padding:1rem;border-radius:var(--radius-md);border-top:3px solid var(--text-muted);">
                            <h5 style="font-weight:700;margin-bottom:0.5rem;color:var(--text-muted);">Previous Review</h5>
                            <p style="font-size:0.8rem;color:var(--text-secondary);margin-bottom:1rem;white-space:pre-wrap;">${dom.escape(pr.previous_review_summary || "No summary")}</p>
                            <div style="font-size:0.8rem;color:var(--text-muted);font-weight:600;margin-bottom:0.5rem;">Previous Issues Found (${prevIssues?.length || 0}):</div>
                            <ul style="font-size:0.8rem;color:var(--text-muted);padding-left:1.2rem;">
                                ${prevIssues && prevIssues.length > 0 ? prevIssues.map(i => `<li>${dom.escape(i.title || i.description)}</li>`).join("") : '<li>No issues</li>'}
                            </ul>
                        </div>
                        <div style="background:rgba(255,255,255,0.02);padding:1rem;border-radius:var(--radius-md);border-top:3px solid var(--primary);">
                            <h5 style="font-weight:700;margin-bottom:0.5rem;color:var(--primary);">Current Review</h5>
                            <p style="font-size:0.8rem;color:var(--text-primary);margin-bottom:1rem;white-space:pre-wrap;">${dom.escape(summary)}</p>
                            <div style="font-size:0.8rem;color:var(--text-primary);font-weight:600;margin-bottom:0.5rem;">New / Active Issues Found (${issues.length}):</div>
                            <ul style="font-size:0.8rem;color:var(--text-primary);padding-left:1.2rem;">
                                ${issues.length > 0 ? issues.map(i => `<li>${dom.escape(i.title || i.description)}</li>`).join("") : '<li>No issues</li>'}
                            </ul>
                        </div>
                    </div>
                </div>
            ` : `
                <!-- Developer Mode Raw JSON Viewer -->
                <div class="glass-card" style="padding:1rem;">
                    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.75rem;">
                        <h4 style="font-size:0.85rem;font-weight:700;color:var(--text-secondary);text-transform:uppercase;">Raw JSON Payload</h4>
                        <button type="button" id="copy-json-btn" class="btn btn-secondary" style="font-size:0.75rem;padding:0.25rem 0.65rem;">
                            📋 Copy JSON
                        </button>
                    </div>
                    <pre style="background:rgba(0,0,0,0.4);padding:1rem;border-radius:var(--radius-md);overflow-x:auto;font-family:monospace;font-size:0.8rem;color:#38bdf8;max-height:450px;"><code>${dom.escape(JSON.stringify(pr, null, 2))}</code></pre>
                </div>
            `}
        `;
    }

    container.innerHTML = buildDrawerHTML();

    function _bindDrawerEvents() {
        container.querySelector("#close-drawer-btn")?.addEventListener("click", () => mount.innerHTML = "");
        
        container.querySelector("#tab-insights-btn")?.addEventListener("click", () => {
            viewMode = 'insights';
            container.innerHTML = buildDrawerHTML();
            _bindDrawerEvents();
        });
        
        container.querySelector("#tab-comparison-btn")?.addEventListener("click", () => {
            viewMode = 'comparison';
            container.innerHTML = buildDrawerHTML();
            _bindDrawerEvents();
        });

        container.querySelector("#tab-devmode-btn")?.addEventListener("click", () => {
            viewMode = 'dev';
            container.innerHTML = buildDrawerHTML();
            _bindDrawerEvents();
        });
        
        container.querySelector("#copy-json-btn")?.addEventListener("click", () => {
            navigator.clipboard.writeText(JSON.stringify(pr, null, 2));
            Toast.success("Raw JSON copied to clipboard.");
        });
    }

    _bindDrawerEvents();
}

function _pct(val, total) {
    if (!total || total === 0) return 0;
    return Math.min(100, Math.round(((val || 0) / total) * 100));
}
