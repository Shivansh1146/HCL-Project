/**
 * pages/pull_requests.js — Enterprise AI Pull Request Review Dashboard.
 *
 * Requirements:
 *  - Pull Request Dashboard List (Open, Merged, Closed, Processing)
 *  - Filters: Decision status (BLOCK, SAFE, PERFECT, REVIEW_REQUIRED), Repository filter
 *  - Search: Debounced search by title or PR number
 *  - PR Detail Drawer/Modal: Files changed, severity breakdown, inline line numbers, suggested fix
 *  - Review Actions: Trigger / Re-run AI review, Cancel review, View History
 *  - Skeleton loaders & WCAG keyboard accessibility
 */

import { store }           from "../utils/state.js";
import { api }             from "../services/api.js";
import { dom }             from "../utils/dom.js";
import { renderSkeleton }  from "../components/skeleton.js";
import { renderEmptyState } from "../components/empty_state.js";
import { Toast }           from "../components/toast.js";

let _prsState = {
    prs: [],
    total: 0,
    activeStatusFilter: "all", // all, success, pending, error
    activeDecisionFilter: "all", // all, BLOCK, SAFE, PERFECT, REVIEW_REQUIRED
    searchQuery: "",
    selectedRepo: "",
    isLoading: false,
    selectedPrDetail: null,
    isDetailLoading: false,
    isReviewing: false,
};

let _debounceTimer = null;

/**
 * Renders the Pull Requests Dashboard page into outlet.
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
                AI Pull Request Review Center
            </h1>
            <p style="color:var(--text-secondary);font-size:0.95rem;">
                Automated Security, Bug, & Performance Analysis for GitHub Pull Requests
            </p>
        </div>
        <div style="display:flex;align-items:center;gap:0.75rem;">
            <button type="button" id="prs-refresh-btn" class="btn btn-secondary" style="gap:0.5rem;" aria-label="Refresh PR list">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 11-.57-8.38l5.67-5.67"/></svg>
                <span>Refresh</span>
            </button>
        </div>
    `;

    // Root containers
    const toolbarEl = document.createElement("div");
    toolbarEl.id = "prs-toolbar-container";

    const listEl = document.createElement("div");
    listEl.id = "prs-list-container";

    const detailModalEl = document.createElement("div");
    detailModalEl.id = "prs-detail-modal-container";

    wrapper.append(header, toolbarEl, listEl, detailModalEl);
    outlet.appendChild(wrapper);

    // Initial Data Fetch
    await _loadPullRequests();
}

async function _loadPullRequests() {
    _prsState.isLoading = true;
    _renderSkeletonState();

    try {
        const stats = await api.getStats();
        const recent = stats?.recent_reviews || [];

        _prsState.prs = recent;
        _prsState.total = recent.length;
    } catch (err) {
        console.error("[PRs] Failed to load PR reviews:", err);
        Toast.error("Failed to load pull request reviews.");
    } finally {
        _prsState.isLoading = false;
        _renderToolbar();
        _renderPrList();
    }
}

function _renderSkeletonState() {
    const listEl = document.getElementById("prs-list-container");
    if (listEl) {
        listEl.innerHTML = `
            <div style="display:flex;flex-direction:column;gap:1rem;">
                ${renderSkeleton("card")}
                ${renderSkeleton("card")}
                ${renderSkeleton("card")}
            </div>
        `;
    }
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
        <input type="text" id="prs-search-input" class="form-input" placeholder="Search PR by repo or number…"
               value="${dom.escape(_prsState.searchQuery)}" aria-label="Search pull requests" style="padding-left:2.5rem;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="position:absolute;left:0.9rem;top:50%;transform:translateY(-50%);color:var(--text-muted);"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    `;

    const searchInput = searchWrap.querySelector("#prs-search-input");
    searchInput.addEventListener("input", (e) => {
        clearTimeout(_debounceTimer);
        _debounceTimer = setTimeout(() => {
            _prsState.searchQuery = e.target.value;
            _renderPrList();
        }, 200);
    });

    // Decision Filter
    const decisionSelect = document.createElement("select");
    decisionSelect.className = "form-select";
    decisionSelect.setAttribute("aria-label", "Filter by decision status");
    decisionSelect.innerHTML = `
        <option value="all" ${_prsState.activeDecisionFilter === "all" ? "selected" : ""}>All Decisions</option>
        <option value="BLOCK" ${_prsState.activeDecisionFilter === "BLOCK" ? "selected" : ""}>🚨 Blocked</option>
        <option value="SAFE" ${_prsState.activeDecisionFilter === "SAFE" ? "selected" : ""}>✅ Safe</option>
        <option value="PERFECT" ${_prsState.activeDecisionFilter === "PERFECT" ? "selected" : ""}>🌟 Perfect</option>
        <option value="REVIEW_REQUIRED" ${_prsState.activeDecisionFilter === "REVIEW_REQUIRED" ? "selected" : ""}>⚠️ Review Required</option>
    `;
    decisionSelect.addEventListener("change", (e) => {
        _prsState.activeDecisionFilter = e.target.value;
        _renderPrList();
    });

    card.append(searchWrap, decisionSelect);
    container.appendChild(card);
}

function _renderPrList() {
    const container = document.getElementById("prs-list-container");
    if (!container) return;

    container.innerHTML = "";
    const filtered = _getFilteredPrs();

    if (filtered.length === 0) {
        renderEmptyState(container, {
            title: "No Pull Requests Found",
            description: _prsState.searchQuery
                ? `No pull request reviews matching "${dom.escape(_prsState.searchQuery)}".`
                : "No PR reviews recorded yet. Webhooks will automatically analyze incoming PRs.",
            icon: `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5"/></svg>`
        });
        return;
    }

    const listWrapper = document.createElement("div");
    listWrapper.style.cssText = "display:flex;flex-direction:column;gap:1rem;";

    filtered.forEach(pr => {
        const card = document.createElement("div");
        card.className = "glass-card animate-fade-up";
        card.style.cssText = "padding:1.25rem 1.5rem;display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;";

        const decisionBadge = _getDecisionBadge(pr.decision);
        const safeRepo = dom.escape(pr.repo);
        const safeDate = dom.escape(new Date(pr.reviewed_at || Date.now()).toLocaleString());

        const left = document.createElement("div");
        left.style.cssText = "display:flex;align-items:center;gap:1.25rem;flex:1;min-width:280px;";

        left.innerHTML = `
            <div style="width:42px;height:42px;border-radius:10px;background:rgba(59,130,246,0.12);color:var(--primary);display:flex;align-items:center;justify-content:center;font-weight:700;flex-shrink:0;">
                #${pr.pr_number}
            </div>
            <div>
                <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.25rem;flex-wrap:wrap;">
                    <strong style="font-size:1.05rem;color:var(--text-primary);">${safeRepo} #${pr.pr_number}</strong>
                    ${decisionBadge}
                </div>
                <div style="font-size:0.8rem;color:var(--text-muted);display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap;">
                    <span>Reviewed: ${safeDate}</span>
                    <span>·</span>
                    <span>Issues: <strong style="color:var(--text-primary);">${pr.issue_count || 0}</strong></span>
                    <span>·</span>
                    <span style="color:var(--color-error);">H: ${pr.severities?.high || 0}</span>
                    <span style="color:var(--color-warning);">M: ${pr.severities?.medium || 0}</span>
                    <span style="color:var(--color-info);">L: ${pr.severities?.low || 0}</span>
                </div>
            </div>
        `;

        const right = document.createElement("div");
        right.style.cssText = "display:flex;align-items:center;gap:0.75rem;";

        const viewBtn = document.createElement("button");
        viewBtn.type = "button";
        viewBtn.className = "btn btn-secondary";
        viewBtn.style.cssText = "gap:0.5rem;padding:0.45rem 1rem;font-size:0.85rem;";
        viewBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg> View Analysis`;

        viewBtn.addEventListener("click", () => _openPrDetailModal(pr));

        right.appendChild(viewBtn);
        card.append(left, right);
        listWrapper.appendChild(card);
    });

    container.appendChild(listWrapper);
}

function _getFilteredPrs() {
    return _prsState.prs.filter(pr => {
        if (_prsState.searchQuery) {
            const q = _prsState.searchQuery.toLowerCase();
            const matchRepo = pr.repo.toLowerCase().includes(q);
            const matchPrNum = String(pr.pr_number).includes(q);
            if (!matchRepo && !matchPrNum) return false;
        }

        if (_prsState.activeDecisionFilter !== "all") {
            if (pr.decision !== _prsState.activeDecisionFilter) return false;
        }

        return true;
    });
}

function _getDecisionBadge(decision) {
    switch (decision) {
        case "PERFECT":
            return `<span class="badge badge-success">🌟 PERFECT</span>`;
        case "SAFE":
            return `<span class="badge badge-success">✅ SAFE</span>`;
        case "REVIEW_REQUIRED":
            return `<span class="badge badge-warning">⚠️ REVIEW REQUIRED</span>`;
        case "BLOCK":
        default:
            return `<span class="badge badge-error">🚨 BLOCKED</span>`;
    }
}

/**
 * Detailed PR Review Modal
 */
function _openPrDetailModal(pr) {
    const modalContainer = document.getElementById("prs-detail-modal-container");
    if (!modalContainer) return;

    modalContainer.innerHTML = "";

    const backdrop = document.createElement("div");
    backdrop.style.cssText = "position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);backdrop-filter:blur(6px);z-index:999;display:flex;align-items:center;justify-content:center;padding:1.5rem;";

    const modal = document.createElement("div");
    modal.className = "glass-card animate-fade-up";
    modal.style.cssText = "width:100%;max-width:850px;max-height:85vh;overflow-y:auto;padding:2rem;display:flex;flex-direction:column;gap:1.5rem;";

    const safeRepo = dom.escape(pr.repo);
    const safeDate = dom.escape(new Date(pr.reviewed_at || Date.now()).toLocaleString());
    const issues = pr.issues || [];

    modal.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border-color);padding-bottom:1rem;">
            <div>
                <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.25rem;">
                    <h2 style="font-size:1.3rem;font-weight:800;">${safeRepo} #${pr.pr_number} Analysis</h2>
                    ${_getDecisionBadge(pr.decision)}
                </div>
                <p style="font-size:0.85rem;color:var(--text-secondary);">Reviewed at: ${safeDate} · AI Model: Groq Llama-3 70B</p>
            </div>
            <button type="button" id="close-modal-btn" class="btn btn-ghost" style="font-size:1.2rem;padding:0.25rem 0.5rem;" aria-label="Close modal">✕</button>
        </div>

        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(160px, 1fr));gap:1rem;padding:1rem;background:rgba(255,255,255,0.02);border:1px solid var(--border-color);border-radius:10px;">
            <div>
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;">Decision</span>
                <strong style="font-size:1rem;">${dom.escape(pr.decision)}</strong>
            </div>
            <div>
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;">High Severity</span>
                <strong style="font-size:1rem;color:var(--color-error);">${pr.severities?.high || 0}</strong>
            </div>
            <div>
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;">Medium Severity</span>
                <strong style="font-size:1rem;color:var(--color-warning);">${pr.severities?.medium || 0}</strong>
            </div>
            <div>
                <span style="font-size:0.75rem;color:var(--text-muted);display:block;">Low Severity</span>
                <strong style="font-size:1rem;color:var(--color-info);">${pr.severities?.low || 0}</strong>
            </div>
        </div>

        <div>
            <h3 style="font-size:1.05rem;font-weight:700;margin-bottom:1rem;">Detected Code Issues (${issues.length})</h3>
            <div style="display:flex;flex-direction:column;gap:1rem;">
                ${issues.length > 0 ? issues.map(iss => `
                    <div style="padding:1rem;background:rgba(255,255,255,0.02);border:1px solid var(--border-color);border-radius:10px;">
                        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.5rem;">
                            <strong style="font-size:0.95rem;color:var(--text-primary);">${dom.escape(iss.title || 'Security/Code Finding')}</strong>
                            <span class="badge ${iss.severity === 'high' ? 'badge-error' : (iss.severity === 'medium' ? 'badge-warning' : 'badge-info')}">
                                ${dom.escape(iss.severity?.toUpperCase() || 'LOW')}
                            </span>
                        </div>
                        <p style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:0.5rem;">${dom.escape(iss.description || '')}</p>
                        <div style="font-size:0.75rem;color:var(--text-muted);font-family:monospace;background:rgba(0,0,0,0.3);padding:0.4rem 0.6rem;border-radius:6px;">
                            📄 File: ${dom.escape(iss.file || 'unknown')} : Line ${iss.line || 0}
                        </div>
                    </div>
                `).join("") : `
                    <div style="text-align:center;padding:2rem;color:var(--text-muted);font-size:0.9rem;">
                        ✨ Zero issues detected! Code is clean and meets all security policies.
                    </div>
                `}
            </div>
        </div>

        <div style="display:flex;align-items:center;justify-content:flex-end;gap:0.75rem;border-top:1px solid var(--border-color);padding-top:1rem;">
            <button type="button" id="rerun-review-btn" class="btn btn-primary" style="gap:0.5rem;">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 11-.57-8.38l5.67-5.67"/></svg>
                Re-run AI Analysis
            </button>
            <button type="button" id="close-modal-footer-btn" class="btn btn-secondary">Close</button>
        </div>
    `;

    const closeModal = () => { modalContainer.innerHTML = ""; };

    modal.querySelector("#close-modal-btn")?.addEventListener("click", closeModal);
    modal.querySelector("#close-modal-footer-btn")?.addEventListener("click", closeModal);
    backdrop.addEventListener("click", (e) => { if (e.target === backdrop) closeModal(); });

    const rerunBtn = modal.querySelector("#rerun-review-btn");
    rerunBtn?.addEventListener("click", async () => {
        rerunBtn.disabled = true;
        rerunBtn.innerHTML = `<div class="spinner" style="width:14px;height:14px;"></div> Queuing…`;
        try {
            const parts = pr.repo.split("/");
            if (parts.length === 2) {
                await api.triggerPullRequestReview(parts[0], parts[1], pr.pr_number);
                Toast.success(`AI Code Review queued for PR #${pr.pr_number}`);
                closeModal();
                await _loadPullRequests();
            }
        } catch (err) {
            Toast.error(err?.message || "Failed to trigger review re-run.");
        } finally {
            rerunBtn.disabled = false;
        }
    });

    backdrop.appendChild(modal);
    modalContainer.appendChild(backdrop);
}
