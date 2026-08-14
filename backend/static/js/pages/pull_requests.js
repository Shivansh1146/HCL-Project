/**
 * pages/pull_requests.js — Pull Request Event Processing & Monitoring Dashboard.
 *
 * Displays ingested GitHub pull request webhook events in an enterprise dashboard:
 *  - Repository, PR #, Title, Author, State, Draft, AI Review Status, Updated Timestamp
 *
 * Includes state filters (All, Open, Merged, Closed, Draft), stats cards, debounced search,
 * paginated table rendering, and Publish Review action buttons.
 */

import { api }             from "../services/api.js";
import { dom }             from "../utils/dom.js";
import { renderSkeleton }  from "../components/skeleton.js";
import { renderEmptyState } from "../components/empty_state.js";
import { Toast }           from "../components/toast.js";

let _prsState = {
    items: [],
    total: 0,
    page: 1,
    perPage: 20,
    totalPages: 1,
    activeStateFilter: "all",
    searchQuery: "",
    isLoading: false,
    stats: {
        total: 0,
        open: 0,
        closed: 0,
        merged: 0,
        draft: 0
    }
};

let _debounceTimer = null;
let _pollInterval = null;

function _startPolling() {
    _stopPolling();
    _pollInterval = setInterval(async () => {
        if (document.visibilityState !== "visible") return;
        try {
            await _loadPullRequests(true);
        } catch (e) {
            // silent fail on auto-refresh
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
 * Main render entry point for Pull Requests page.
 * @param {HTMLElement} outlet
 */
export async function renderPullRequestsPage(outlet) {
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
                Pull Request Dashboard
            </h1>
            <p style="color:var(--text-secondary);font-size:0.95rem;">
                Monitored GitHub Pull Request Webhook Events & Lifecycle Tracking
            </p>
        </div>
        <div style="display:flex;align-items:center;gap:0.75rem;">
            <button type="button" id="prs-refresh-btn" class="btn btn-secondary" style="gap:0.5rem;" aria-label="Refresh PR list">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 11-.57-8.38l5.67-5.67"/></svg>
                <span>Refresh</span>
            </button>
        </div>
    `;

    const refreshBtn = header.querySelector("#prs-refresh-btn");
    refreshBtn?.addEventListener("click", async () => {
        refreshBtn.disabled = true;
        await _loadPullRequests();
        refreshBtn.disabled = false;
    });

    // Root containers
    const statsEl = document.createElement("div");
    statsEl.id = "prs-stats-container";

    const toolbarEl = document.createElement("div");
    toolbarEl.id = "prs-toolbar-container";

    const tableEl = document.createElement("div");
    tableEl.id = "prs-table-container";

    wrapper.append(header, statsEl, toolbarEl, tableEl);
    outlet.appendChild(wrapper);

    // Refresh Listener
    header.querySelector("#prs-refresh-btn")?.addEventListener("click", async () => {
        await _loadPullRequests();
        Toast.success("Pull request data refreshed.");
    });

    // Initial Data Fetch
    await _loadPullRequests();

    window.addEventListener("router:before-navigate", _stopPolling, { once: true });
    _startPolling();
}

async function _loadPullRequests(silent = false) {
    if (!silent) {
        _prsState.isLoading = true;
        _renderSkeletonState();
    }

    try {
        const [prRes, statsRes] = await Promise.allSettled([
            api.getPullRequests({
                page: _prsState.page,
                per_page: _prsState.perPage,
                state: _prsState.activeStateFilter
            }),
            api.getPullRequestStats()
        ]);

        if (prRes.status === "fulfilled" && prRes.value) {
            _prsState.items = prRes.value.items || [];
            _prsState.total = prRes.value.total || 0;
            _prsState.totalPages = prRes.value.total_pages || 1;
        } else if (!silent) {
            _prsState.items = [];
            _prsState.total = 0;
        }

        if (statsRes.status === "fulfilled" && statsRes.value) {
            _prsState.stats = statsRes.value;
        }
    } catch (err) {
        console.error("[PRs] Failed to load PRs:", err);
        if (!silent) Toast.error("Failed to load pull requests.");
    } finally {
        if (!silent) _prsState.isLoading = false;
        _renderStatsCards();
        if (!silent) _renderToolbar();
        _renderPrTable();
    }
}

function _renderSkeletonState() {
    const tableEl = document.getElementById("prs-table-container");
    if (tableEl) {
        tableEl.innerHTML = `
            <div style="display:flex;flex-direction:column;gap:1rem;">
                ${renderSkeleton("table")}
            </div>
        `;
    }
}

function _renderStatsCards() {
    const container = document.getElementById("prs-stats-container");
    if (!container) return;

    const s = _prsState.stats;
    container.innerHTML = `
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(160px, 1fr));gap:1rem;margin-bottom:1.5rem;">
            <div class="glass-card" style="padding:1rem 1.25rem;">
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">Total Ingested PRs</span>
                <strong style="font-size:1.5rem;font-weight:800;color:var(--text-primary);">${s.total}</strong>
            </div>
            <div class="glass-card" style="padding:1rem 1.25rem;">
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">Open PRs</span>
                <strong style="font-size:1.5rem;font-weight:800;color:var(--primary);">${s.open}</strong>
            </div>
            <div class="glass-card" style="padding:1rem 1.25rem;">
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">Merged PRs</span>
                <strong style="font-size:1.5rem;font-weight:800;color:var(--color-success);">${s.merged}</strong>
            </div>
            <div class="glass-card" style="padding:1rem 1.25rem;">
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">Closed PRs</span>
                <strong style="font-size:1.5rem;font-weight:800;color:var(--text-muted);">${s.closed}</strong>
            </div>
            <div class="glass-card" style="padding:1rem 1.25rem;">
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">Draft PRs</span>
                <strong style="font-size:1.5rem;font-weight:800;color:var(--color-warning);">${s.draft}</strong>
            </div>
        </div>
    `;
}

function _renderToolbar() {
    const container = document.getElementById("prs-toolbar-container");
    if (!container) return;

    container.innerHTML = "";
    const card = document.createElement("div");
    card.className = "glass-card";
    card.style.cssText = "margin-bottom:1.5rem;padding:1rem 1.25rem;display:flex;align-items:center;gap:1rem;flex-wrap:wrap;";

    // Search Input
    const searchWrap = document.createElement("div");
    searchWrap.style.cssText = "flex:1;min-width:240px;position:relative;";
    searchWrap.innerHTML = `
        <input type="text" id="prs-search-input" class="form-input" placeholder="Search by title, repo, or author…"
               value="${dom.escape(_prsState.searchQuery)}" aria-label="Search pull requests" style="padding-left:2.5rem;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="position:absolute;left:0.9rem;top:50%;transform:translateY(-50%);color:var(--text-muted);"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    `;

    const searchInput = searchWrap.querySelector("#prs-search-input");
    searchInput.addEventListener("input", (e) => {
        clearTimeout(_debounceTimer);
        _debounceTimer = setTimeout(() => {
            _prsState.searchQuery = e.target.value;
            _renderPrTable();
        }, 200);
    });

    // State Filter Dropdown
    const stateSelect = document.createElement("select");
    stateSelect.className = "form-select";
    stateSelect.setAttribute("aria-label", "Filter by PR state");
    stateSelect.innerHTML = `
        <option value="all" ${_prsState.activeStateFilter === "all" ? "selected" : ""}>All States</option>
        <option value="open" ${_prsState.activeStateFilter === "open" ? "selected" : ""}>🟢 Open</option>
        <option value="merged" ${_prsState.activeStateFilter === "merged" ? "selected" : ""}>🟣 Merged</option>
        <option value="closed" ${_prsState.activeStateFilter === "closed" ? "selected" : ""}>🔴 Closed</option>
        <option value="draft" ${_prsState.activeStateFilter === "draft" ? "selected" : ""}>📝 Draft</option>
    `;

    stateSelect.addEventListener("change", async (e) => {
        _prsState.activeStateFilter = e.target.value;
        _prsState.page = 1;
        await _loadPullRequests();
    });

    card.append(searchWrap, stateSelect);
    container.appendChild(card);
}

function _renderPrTable() {
    const container = document.getElementById("prs-table-container");
    if (!container) return;

    container.innerHTML = "";
    const items = _getFilteredItems();

    if (items.length === 0) {
        renderEmptyState(container, {
            title: "No Pull Requests Found",
            description: _prsState.searchQuery
                ? `No pull requests matching "${dom.escape(_prsState.searchQuery)}".`
                : "No PR webhook events received yet. Once your GitHub App receives pull request events, they will automatically appear here.",
            icon: `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 012 2v7M6 9v12"/></svg>`
        });
        return;
    }

    const tableCard = document.createElement("div");
    tableCard.className = "glass-card";
    tableCard.style.cssText = "overflow-x:auto;";

    const table = document.createElement("table");
    table.style.cssText = "width:100%;border-collapse:collapse;text-align:left;font-size:0.9rem;";

    table.innerHTML = `
        <thead>
            <tr style="border-bottom:1px solid var(--border-color);color:var(--text-muted);font-size:0.8rem;text-transform:uppercase;letter-spacing:0.05em;">
                <th style="padding:1rem;">Repository</th>
                <th style="padding:1rem;">PR #</th>
                <th style="padding:1rem;">Title</th>
                <th style="padding:1rem;">Author</th>
                <th style="padding:1rem;">State</th>
                <th style="padding:1rem;">AI Review</th>
                <th style="padding:1rem;">Published</th>
                <th style="padding:1rem;">Updated</th>
                <th style="padding:1rem;">Actions</th>
            </tr>
        </thead>
        <tbody>
            ${items.map(pr => {
                const repoName = dom.escape(pr.repository_name || `${pr.owner}/${pr.repository_name}`);
                const title = dom.escape(pr.title || "Untitled Pull Request");
                const author = dom.escape(pr.author_login || "unknown");
                const stateBadge = _getStateBadge(pr);
                const updatedTime = dom.escape(new Date(pr.updated_at || pr.created_at || Date.now()).toLocaleString());
                const prUrl = pr.html_url ? dom.escape(pr.html_url) : "#";
                const aiReviewBadge = _getAIReviewBadge(pr);
                const publishedBadge = _getPublishedBadge(pr);
                const owner = dom.escape(pr.owner || "");
                const repoOnly = dom.escape((pr.repository_name || "").split("/").pop() || pr.repository_name);
                const canPublish = pr.review_status === "success" && !pr.review_posted;

                return `
                    <tr style="border-bottom:1px solid var(--border-color);transition:background 0.2s;" class="table-row-hover">
                        <td style="padding:1rem;font-weight:600;color:var(--text-primary);">${repoName}</td>
                        <td style="padding:1rem;">
                            <a href="${prUrl}" target="_blank" rel="noopener noreferrer" style="color:var(--primary);font-weight:700;text-decoration:none;">
                                #${pr.number}
                            </a>
                        </td>
                        <td style="padding:1rem;max-width:260px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${title}">
                            ${title}
                        </td>
                        <td style="padding:1rem;color:var(--text-secondary);">
                            <div style="display:flex;align-items:center;gap:0.5rem;">
                                ${pr.author_avatar ? `<img src="${dom.escape(pr.author_avatar)}" alt="${author}" style="width:22px;height:22px;border-radius:50%;">` : ""}
                                <span>${author}</span>
                            </div>
                        </td>
                        <td style="padding:1rem;">${stateBadge}</td>
                        <td style="padding:1rem;">${aiReviewBadge}</td>
                        <td style="padding:1rem;">${publishedBadge}</td>
                        <td style="padding:1rem;color:var(--text-muted);font-size:0.8rem;">${updatedTime}</td>
                        <td style="padding:1rem;">
                            ${canPublish ? `
                            <button
                                type="button"
                                class="btn btn-primary"
                                style="font-size:0.78rem;padding:0.3rem 0.7rem;gap:0.35rem;"
                                id="publish-btn-${pr.number}"
                                data-owner="${owner}"
                                data-repo="${repoOnly}"
                                data-pr-number="${pr.number}"
                                aria-label="Publish AI review to GitHub for PR #${pr.number}"
                            >
                                📤 Publish
                            </button>
                            ` : `<span style="color:var(--text-muted);font-size:0.78rem;">—</span>`}
                        </td>
                    </tr>
                `;
            }).join("")}
        </tbody>
    `;

    // Attach Publish Review button handlers
    table.querySelectorAll("[id^='publish-btn-']").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            const { owner, repo, prNumber } = btn.dataset;
            await _publishReview(owner, repo, parseInt(prNumber, 10), btn);
        });
    });

    tableCard.appendChild(table);
    container.appendChild(tableCard);
}

function _getFilteredItems() {
    if (!_prsState.searchQuery) return _prsState.items;
    const q = _prsState.searchQuery.toLowerCase();
    return _prsState.items.filter(item => {
        const titleMatch = (item.title || "").toLowerCase().includes(q);
        const repoMatch = (item.repository_name || "").toLowerCase().includes(q);
        const authorMatch = (item.author_login || "").toLowerCase().includes(q);
        const numberMatch = String(item.number).includes(q);
        return titleMatch || repoMatch || authorMatch || numberMatch;
    });
}

function _getStateBadge(pr) {
    if (pr.merged) {
        return `<span class="badge badge-purple" style="background:rgba(168,85,247,0.15);color:#c084fc;border:1px solid rgba(168,85,247,0.3);">🟣 Merged</span>`;
    }
    if (pr.state === "closed") {
        return `<span class="badge badge-error">🔴 Closed</span>`;
    }
    if (pr.draft) {
        return `<span class="badge badge-warning">📝 Draft</span>`;
    }
    return `<span class="badge badge-success">🟢 Open</span>`;
}

function _getAIReviewBadge(pr) {
    const status = pr.review_status || "pending";
    const decision = pr.decision || "";

    const decisionColors = {
        "SAFE":             { bg: "rgba(16,185,129,0.15)", color: "#10b981", border: "rgba(16,185,129,0.3)", emoji: "✅" },
        "REVIEW_REQUIRED":  { bg: "rgba(245,158,11,0.15)", color: "#f59e0b", border: "rgba(245,158,11,0.3)",  emoji: "⚠️" },
        "BLOCK":            { bg: "rgba(239,68,68,0.15)",  color: "#ef4444", border: "rgba(239,68,68,0.3)",   emoji: "🚫" },
        "ANALYSIS_INCOMPLETE": { bg: "rgba(107,114,128,0.15)", color: "#9ca3af", border: "rgba(107,114,128,0.3)", emoji: "⏭️" },
    };
    const statusColors = {
        "pending":    { bg: "rgba(107,114,128,0.15)", color: "#9ca3af", border: "rgba(107,114,128,0.3)", label: "⏳ Pending" },
        "processing": { bg: "rgba(59,130,246,0.15)",  color: "#3b82f6", border: "rgba(59,130,246,0.3)",  label: "🔄 Processing" },
        "failed":     { bg: "rgba(239,68,68,0.15)",   color: "#ef4444", border: "rgba(239,68,68,0.3)",   label: "💥 Failed" },
    };

    if (status === "success" && decision && decisionColors[decision]) {
        const c = decisionColors[decision];
        const issues = pr.issues_count || 0;
        return `<span style="display:inline-flex;align-items:center;gap:0.3rem;padding:0.2rem 0.6rem;border-radius:9999px;font-size:0.75rem;font-weight:600;background:${c.bg};color:${c.color};border:1px solid ${c.border};">${c.emoji} ${decision}${issues > 0 ? ` (${issues})` : ""}</span>`;
    }
    if (statusColors[status]) {
        const c = statusColors[status];
        return `<span style="display:inline-flex;align-items:center;gap:0.3rem;padding:0.2rem 0.6rem;border-radius:9999px;font-size:0.75rem;font-weight:600;background:${c.bg};color:${c.color};border:1px solid ${c.border};">${c.label}</span>`;
    }
    return `<span style="color:var(--text-muted);font-size:0.78rem;">—</span>`;
}

function _getPublishedBadge(pr) {
    if (pr.review_posted) {
        const reviewId = pr.github_review_id ? `#${pr.github_review_id}` : "";
        const postedAt = pr.review_posted_at ? new Date(pr.review_posted_at).toLocaleString() : "";
        return `<span title="Published to GitHub ${postedAt}" style="display:inline-flex;align-items:center;gap:0.3rem;padding:0.2rem 0.6rem;border-radius:9999px;font-size:0.75rem;font-weight:600;background:rgba(16,185,129,0.15);color:#10b981;border:1px solid rgba(16,185,129,0.3);">✅ Published ${reviewId}</span>`;
    }
    if (pr.review_status === "success") {
        return `<span style="display:inline-flex;align-items:center;padding:0.2rem 0.6rem;border-radius:9999px;font-size:0.75rem;font-weight:600;background:rgba(107,114,128,0.12);color:#9ca3af;border:1px solid rgba(107,114,128,0.25);">Not Published</span>`;
    }
    return `<span style="color:var(--text-muted);font-size:0.78rem;">—</span>`;
}

async function _publishReview(owner, repo, prNumber, btn) {
    if (!btn) return;
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span style="opacity:0.7;">⏳ Publishing…</span>`;
    try {
        const result = await api.publishPullRequestReview(owner, repo, prNumber);
        if (result.status === "success" || result.status === "already_published") {
            const reviewId = result.review_id ? ` (Review #${result.review_id})` : "";
            const comments = result.comments_posted != null ? `, ${result.comments_posted} comment(s)` : "";
            Toast.success(`✅ Review published to GitHub${reviewId}${comments}`);
            await _loadPullRequests();
        } else {
            Toast.error(result.error || "Review publish returned an unexpected status.");
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    } catch (err) {
        console.error("[PRs] publish review error:", err);
        Toast.error(err?.message || "Failed to publish review to GitHub.");
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}
