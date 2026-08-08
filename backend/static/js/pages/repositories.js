/**
 * pages/repositories.js — Enterprise Repository & Organization Management Page.
 *
 * Requirements:
 *  - Installation & Organization Switcher (Personal Account & Organizations)
 *  - Repository List with avatars, visibility, language, stars, AI review status
 *  - Instant debounced search (by name or owner)
 *  - Filters: Visibility (Public/Private), AI Selection (Selected/Unselected), Language
 *  - Sorting: Alphabetical, Stars, Name
 *  - Pagination: 10, 25, 50, 100 items per page with page controls
 *  - Bulk Selection: Select All, Clear All, Enable/Disable Review for current list, Save Repository Settings with unsaved indicator
 *  - GitHub App Status Card with sync/reinstall triggers
 *  - Skeleton loaders & Accessible WCAG design
 */

import { renderAppStatusCard } from "../components/app_lifecycle.js";
import { renderEmptyState } from "../components/empty_state.js";
import { renderSkeleton } from "../components/skeleton.js";
import { Toast } from "../components/toast.js";
import { api } from "../services/api.js";
import { dom } from "../utils/dom.js";
import { store } from "../utils/state.js";

// Local state for repository page management
let _state = {
  installations: [],
  appStatus: null,
  selectedInstallationId: null,
  repos: [],
  pendingSelectedRepoNames: new Set(),
  initialSelectedRepoNames: new Set(),
  searchQuery: "",
  filterVisibility: "all", // all, public, private
  filterSelection: "all", // all, selected, unselected
  filterLanguage: "all", // all, or specific language
  sortBy: "name", // name, stars
  pageSize: 10,
  currentPage: 1,
  isLoading: false,
  isSaving: false,
  error: null,
};

let _debounceTimer = null;

/**
 * Renders the Repository & Organization Management page into outlet.
 * @param {HTMLElement} outlet
 */
export async function renderReposPage(outlet) {
  outlet.innerHTML = "";

  const wrapper = document.createElement("div");
  wrapper.className = "animate-fade-up";
  wrapper.style.cssText = "padding:1rem 0 3rem;";

  // Page Header
  const header = document.createElement("div");
  header.style.cssText =
    "margin-bottom:1.5rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem;";
  header.innerHTML = `
        <div>
            <h1 style="font-size:1.75rem;font-weight:800;letter-spacing:-0.03em;margin-bottom:0.25rem;">
                Repository & Organization Management
            </h1>
            <p style="color:var(--text-secondary);font-size:0.95rem;">
                Configure AI code review coverage across GitHub repositories and organizations
            </p>
        </div>
        <div style="display:flex;align-items:center;gap:0.75rem;">
            <button type="button" id="repos-sync-btn" class="btn btn-secondary" style="gap:0.5rem;" aria-label="Sync repositories from GitHub">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 11-.57-8.38l5.67-5.67"/></svg>
                <span>Sync Repos</span>
            </button>
            <a href="#" id="repos-app-link" target="_blank" rel="noopener noreferrer" class="btn btn-github" style="gap:0.5rem;" aria-label="Manage GitHub App installation on GitHub">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
                <span>GitHub App Settings</span>
            </a>
        </div>
    `;

  // Root Containers
  const instBannerEl = document.createElement("div");
  instBannerEl.id = "inst-banner-container";
  instBannerEl.style.marginBottom = "1.5rem";

  const toolbarEl = document.createElement("div");
  toolbarEl.id = "repos-toolbar-container";

  const bulkBarEl = document.createElement("div");
  bulkBarEl.id = "repos-bulkbar-container";

  const listEl = document.createElement("div");
  listEl.id = "repos-list-container";

  const paginationEl = document.createElement("div");
  paginationEl.id = "repos-pagination-container";

  wrapper.append(
    header,
    instBannerEl,
    toolbarEl,
    bulkBarEl,
    listEl,
    paginationEl
  );
  outlet.appendChild(wrapper);

  // Wire the "Sync Repos" button — uses installation token → /api/repositories/sync
  const syncBtn = document.getElementById("repos-sync-btn");
  if (syncBtn) {
    syncBtn.addEventListener("click", async () => {
      const btnSpan = syncBtn.querySelector("span");
      const btnSvg = syncBtn.querySelector("svg");
      syncBtn.disabled = true;
      if (btnSpan) btnSpan.textContent = "Syncing…";
      if (btnSvg) btnSvg.style.animation = "spin 1s linear infinite";

      try {
        const result = await api.syncRepositories();
        Toast.success(
          `Synced ${result.synced_count ?? 0} repositories from GitHub.`
        );
        // Reload the page data from DB after sync
        _state.repos = (result.repositories || []).map((r) => ({
          ...r,
          repo_id: r.repo_id ?? r.id ?? 0,
          enabled: r.enabled ?? true,
        }));
        _state.error = null;
        _renderAllSections();
      } catch (err) {
        console.error("[Repos] Sync failed:", err);
        Toast.error(
          err?.message ||
            "Repository sync failed. Check GitHub App installation."
        );
      } finally {
        syncBtn.disabled = false;
        if (btnSpan) btnSpan.textContent = "Sync Repos";
        if (btnSvg) btnSvg.style.animation = "";
      }
    });
  }

  // Initial Data Fetch — load from DB first, fallback to installation-based load
  await _loadInstallations(outlet);
}

// ---------------------------------------------------------------------------
// Data Fetchers
// ---------------------------------------------------------------------------

async function _loadInstallations(outlet) {
  _state.isLoading = true;
  _renderSkeletonState();

  try {
    const [installations, appStatus] = await Promise.all([
      api.getInstallations(),
      api.getAppStatus().catch(() => null),
    ]);
    _state.installations = installations || [];
    _state.appStatus = appStatus;
    store.setInstallations(_state.installations);

    const appLink = document.getElementById("repos-app-link");
    if (appLink) {
      const installUrl = _state.appStatus?.install_url || "";
      if (installUrl) {
        appLink.href = installUrl;
        appLink.textContent =
          _state.installations.length > 0
            ? "GitHub App Settings"
            : "Install GitHub App";
      } else {
        appLink.href = "#";
        appLink.textContent = "GitHub App Settings";
      }
    }

    if (_state.installations.length > 0) {
      if (!_state.selectedInstallationId) {
        _state.selectedInstallationId = _state.installations[0].installation_id;
      }
      await _loadReposForInstallation(_state.selectedInstallationId);
    } else {
      _state.repos = [];
      _state.isLoading = false;
      _renderAllSections();
    }
  } catch (err) {
    console.error("[Repos] Failed to load installations:", err);
    _state.isLoading = false;
    _state.error = err?.message || "Failed to load GitHub App installations.";
    _renderErrorState(outlet);
  }
}

async function _loadReposForInstallation(instId) {
  _state.isLoading = true;
  _renderSkeletonState();

  try {
    const repos = await api.getReposForInstallation(instId);
    _state.repos = (repos || []).map((r) => ({
      ...r,
      repo_id: r.repo_id ?? r.id ?? 0,
    }));
    _state.error = null;

    // Track initial and pending selected names
    const enabledNames = new Set(
      _state.repos
        .filter((r) => r.enabled)
        .map((r) => r.full_name.toLowerCase())
    );
    _state.initialSelectedRepoNames = new Set(enabledNames);
    _state.pendingSelectedRepoNames = new Set(enabledNames);
  } catch (err) {
    console.error(
      `[Repos] Failed to load repos for installation ${instId}:`,
      err
    );
    _state.error = err?.message || "Failed to fetch repositories.";
    Toast.error(_state.error);
  } finally {
    _state.isLoading = false;
    _renderAllSections();
  }
}

// ---------------------------------------------------------------------------
// Render Methods
// ---------------------------------------------------------------------------

function _renderSkeletonState() {
  const listEl = document.getElementById("repos-list-container");
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

function _renderErrorState(outlet) {
  outlet.innerHTML = "";
  const container = document.createElement("div");
  container.style.cssText = "padding:3rem 1rem;text-align:center;";

  renderEmptyState(container, {
    title: "Repository Connection Error",
    description: _state.error || "Unable to communicate with GitHub App API.",
    icon: `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
    actionText: "Retry Connection",
    onAction: () => renderReposPage(outlet),
  });

  outlet.appendChild(container);
}

function _renderAllSections() {
  _renderInstallationBanner();
  _renderToolbar();
  _renderBulkBar();
  _renderRepoList();
  _renderPagination();
}

/**
 * 1. Installation & Organization Banner
 */
function _renderInstallationBanner() {
  const container = document.getElementById("inst-banner-container");
  if (!container) return;

  container.innerHTML = "";
  const activeInst =
    _state.installations.find(
      (i) => i.installation_id === _state.selectedInstallationId
    ) ||
    _state.installations[0] ||
    null;

  // 1. Render App Status Card / Wizard
  const statusCardContainer = document.createElement("div");
  statusCardContainer.style.marginBottom = "1rem";
  renderAppStatusCard(
    statusCardContainer,
    activeInst,
    async () => {
      if (activeInst) {
        await api.syncInstallation(activeInst.installation_id);
        await _loadReposForInstallation(activeInst.installation_id);
      }
    },
    _state.appStatus?.install_url || ""
  );

  container.appendChild(statusCardContainer);

  // 2. Render Installation Selector Dropdown if multiple installations exist
  if (_state.installations.length > 1) {
    const selectorCard = document.createElement("div");
    selectorCard.className = "glass-card";
    selectorCard.style.cssText =
      "display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem;padding:1rem 1.25rem;";

    const label = document.createElement("span");
    label.style.cssText = "font-size:0.9rem;font-weight:600;";
    label.textContent = "Selected Installation Target:";

    const select = document.createElement("select");
    select.className = "form-select";
    select.style.cssText = "font-weight:600;min-width:240px;";
    select.setAttribute(
      "aria-label",
      "Select GitHub Account / Organization Installation"
    );

    _state.installations.forEach((inst) => {
      const option = document.createElement("option");
      option.value = String(inst.installation_id);
      option.selected = inst.installation_id === _state.selectedInstallationId;
      option.textContent = `${inst.account_login} (${inst.account_type})`;
      select.appendChild(option);
    });

    select.addEventListener("change", async (e) => {
      _state.selectedInstallationId = Number(e.target.value);
      store.setCurrentOrg(
        _state.installations.find(
          (i) => i.installation_id === _state.selectedInstallationId
        )?.account_login || "Personal"
      );
      await _loadReposForInstallation(_state.selectedInstallationId);
    });

    selectorCard.append(label, select);
    container.appendChild(selectorCard);
  }
}

/**
 * 2. Search & Filter Toolbar
 */
function _renderToolbar() {
  const container = document.getElementById("repos-toolbar-container");
  if (!container) return;

  container.innerHTML = "";
  const card = document.createElement("div");
  card.className = "glass-card";
  card.style.cssText =
    "margin-bottom:1rem;padding:1rem 1.25rem;display:flex;align-items:center;gap:1rem;flex-wrap:wrap;";

  // Search Input (Debounced)
  const searchWrap = document.createElement("div");
  searchWrap.style.cssText = "flex:1;min-width:240px;position:relative;";
  searchWrap.innerHTML = `
        <input type="text" id="repos-search-input" class="form-input" placeholder="Search by repository name or owner…"
               value="${dom.escape(
                 _state.searchQuery
               )}" aria-label="Search repositories" style="padding-left:2.5rem;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="position:absolute;left:0.9rem;top:50%;transform:translateY(-50%);color:var(--text-muted);"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    `;

  const searchInput = searchWrap.querySelector("#repos-search-input");
  searchInput.addEventListener("input", (e) => {
    clearTimeout(_debounceTimer);
    _debounceTimer = setTimeout(() => {
      _state.searchQuery = e.target.value;
      _state.currentPage = 1;
      _renderRepoList();
      _renderPagination();
      _renderBulkBar();
    }, 200);
  });

  // Visibility Filter
  const visibilitySelect = document.createElement("select");
  visibilitySelect.className = "form-select";
  visibilitySelect.setAttribute("aria-label", "Filter by visibility");
  visibilitySelect.innerHTML = `
        <option value="all" ${
          _state.filterVisibility === "all" ? "selected" : ""
        }>All Visibilities</option>
        <option value="public" ${
          _state.filterVisibility === "public" ? "selected" : ""
        }>Public Only</option>
        <option value="private" ${
          _state.filterVisibility === "private" ? "selected" : ""
        }>Private Only</option>
    `;
  visibilitySelect.addEventListener("change", (e) => {
    _state.filterVisibility = e.target.value;
    _state.currentPage = 1;
    _renderRepoList();
    _renderPagination();
    _renderBulkBar();
  });

  // AI Review Selection Filter
  const selectionSelect = document.createElement("select");
  selectionSelect.className = "form-select";
  selectionSelect.setAttribute("aria-label", "Filter by AI Review coverage");
  selectionSelect.innerHTML = `
        <option value="all" ${
          _state.filterSelection === "all" ? "selected" : ""
        }>All Coverage</option>
        <option value="selected" ${
          _state.filterSelection === "selected" ? "selected" : ""
        }>AI Enabled</option>
        <option value="unselected" ${
          _state.filterSelection === "unselected" ? "selected" : ""
        }>AI Disabled</option>
    `;
  selectionSelect.addEventListener("change", (e) => {
    _state.filterSelection = e.target.value;
    _state.currentPage = 1;
    _renderRepoList();
    _renderPagination();
    _renderBulkBar();
  });

  // Sorting Select
  const sortSelect = document.createElement("select");
  sortSelect.className = "form-select";
  sortSelect.setAttribute("aria-label", "Sort repositories");
  sortSelect.innerHTML = `
        <option value="name" ${
          _state.sortBy === "name" ? "selected" : ""
        }>Sort: Name (A-Z)</option>
        <option value="stars" ${
          _state.sortBy === "stars" ? "selected" : ""
        }>Sort: Most Stars</option>
    `;
  sortSelect.addEventListener("change", (e) => {
    _state.sortBy = e.target.value;
    _renderRepoList();
    _renderBulkBar();
  });

  card.append(searchWrap, visibilitySelect, selectionSelect, sortSelect);
  container.appendChild(card);
}

/**
 * 3. Bulk Action Bar & Unsaved Changes Alert
 */
function _renderBulkBar() {
  const container = document.getElementById("repos-bulkbar-container");
  if (!container) return;

  container.innerHTML = "";
  const hasUnsaved = _hasUnsavedChanges();
  const filteredRepos = _getFilteredRepos();

  const card = document.createElement("div");
  card.className = "glass-card";
  card.style.cssText = `margin-bottom:1rem;padding:0.85rem 1.25rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem;transition:all 0.2s ease;${
    hasUnsaved
      ? "border-color:var(--primary);box-shadow:0 0 12px rgba(59,130,246,0.2);"
      : ""
  }`;

  const left = document.createElement("div");
  left.style.cssText = "display:flex;align-items:center;gap:0.75rem;";

  const selectAllBtn = document.createElement("button");
  selectAllBtn.type = "button";
  selectAllBtn.className = "btn btn-secondary";
  selectAllBtn.style.cssText = "padding:0.4rem 0.75rem;font-size:0.85rem;";
  selectAllBtn.textContent = "Select All Page";
  selectAllBtn.addEventListener("click", () => {
    const paginated = _getPaginatedRepos(filteredRepos);
    paginated.forEach((r) =>
      _state.pendingSelectedRepoNames.add(r.full_name.toLowerCase())
    );
    _renderBulkBar();
    _renderRepoList();
  });

  const clearAllBtn = document.createElement("button");
  clearAllBtn.type = "button";
  clearAllBtn.className = "btn btn-secondary";
  clearAllBtn.style.cssText = "padding:0.4rem 0.75rem;font-size:0.85rem;";
  clearAllBtn.textContent = "Clear All";
  clearAllBtn.addEventListener("click", () => {
    _state.pendingSelectedRepoNames.clear();
    _renderBulkBar();
    _renderRepoList();
  });

  const bulkEnableBtn = document.createElement("button");
  bulkEnableBtn.type = "button";
  bulkEnableBtn.className = "btn btn-secondary";
  bulkEnableBtn.style.cssText =
    "padding:0.4rem 0.75rem;font-size:0.85rem;color:var(--color-success);";
  bulkEnableBtn.textContent = "Enable Review";
  bulkEnableBtn.title = "Enable AI Review for all repositories currently shown in the list.";
  bulkEnableBtn.disabled = filteredRepos.length === 0;
  bulkEnableBtn.addEventListener("click", () => {
    filteredRepos.forEach((r) =>
      _state.pendingSelectedRepoNames.add(r.full_name.toLowerCase())
    );
    _renderBulkBar();
    _renderRepoList();
  });

  const bulkDisableBtn = document.createElement("button");
  bulkDisableBtn.type = "button";
  bulkDisableBtn.className = "btn btn-secondary";
  bulkDisableBtn.style.cssText =
    "padding:0.4rem 0.75rem;font-size:0.85rem;color:var(--color-error);";
  bulkDisableBtn.textContent = "Disable Review";
  bulkDisableBtn.title = "Disable AI Review for all repositories currently shown in the list.";
  bulkDisableBtn.disabled = filteredRepos.length === 0;
  bulkDisableBtn.addEventListener("click", () => {
    filteredRepos.forEach((r) =>
      _state.pendingSelectedRepoNames.delete(r.full_name.toLowerCase())
    );
    _renderBulkBar();
    _renderRepoList();
  });

  left.append(selectAllBtn, clearAllBtn, bulkEnableBtn, bulkDisableBtn);

  const right = document.createElement("div");
  right.style.cssText = "display:flex;align-items:center;gap:1rem;";

  if (hasUnsaved) {
    const unsavedBadge = document.createElement("span");
    unsavedBadge.className = "badge badge-warning";
    unsavedBadge.textContent = "Unsaved Changes";
    right.appendChild(unsavedBadge);
  }

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "btn btn-primary";
  saveBtn.disabled = !hasUnsaved || _state.isSaving;
  saveBtn.style.cssText = "gap:0.5rem;padding:0.5rem 1.25rem;";
  saveBtn.title = "Save the current repository review configuration.";
  saveBtn.innerHTML = _state.isSaving
    ? `<div class="spinner" style="width:16px;height:16px;"></div> Loading…`
    : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg> Save Repository Settings`;

  saveBtn.addEventListener("click", () => _saveRepoSelections());

  right.appendChild(saveBtn);
  card.append(left, right);
  container.appendChild(card);
}

/**
 * 4. Repository Card List
 */
function _renderRepoList() {
  const container = document.getElementById("repos-list-container");
  if (!container) return;

  container.innerHTML = "";
  const filteredRepos = _getFilteredRepos();

  if (filteredRepos.length === 0) {
    renderEmptyState(container, {
      title: "No Repositories Found",
      description: _state.searchQuery
        ? `No repositories matching "${dom.escape(_state.searchQuery)}".`
        : "No repositories match the selected visibility/coverage filters.",
      icon: `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 3h18v18H3zM3 9h18M9 21V9"/></svg>`,
      actionText: "Reset Search & Filters",
      onAction: () => {
        _state.searchQuery = "";
        _state.filterVisibility = "all";
        _state.filterSelection = "all";
        _state.currentPage = 1;
        _renderAllSections();
      },
    });
    return;
  }

  const paginatedRepos = _getPaginatedRepos(filteredRepos);
  const listWrapper = document.createElement("div");
  listWrapper.style.cssText =
    "display:flex;flex-direction:column;gap:0.75rem;margin-bottom:1.5rem;";

  paginatedRepos.forEach((repo) => {
    const repoFullNameLower = repo.full_name.toLowerCase();
    const isEnabled = _state.pendingSelectedRepoNames.has(repoFullNameLower);
    const parts = repo.full_name.split("/");
    const owner = parts[0] || "";
    const name = parts[1] || repo.full_name;

    const card = document.createElement("div");
    card.className = "glass-card";
    card.style.cssText =
      "padding:1rem 1.25rem;display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;";

    const left = document.createElement("div");
    left.style.cssText =
      "display:flex;align-items:center;gap:1rem;flex:1;min-width:260px;";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = isEnabled;
    checkbox.style.cssText =
      "width:18px;height:18px;cursor:pointer;accent-color:var(--primary);";
    checkbox.setAttribute(
      "aria-label",
      `Enable AI Code Review for ${dom.escape(repo.full_name)}`
    );
    checkbox.addEventListener("change", (e) => {
      if (e.target.checked) {
        _state.pendingSelectedRepoNames.add(repoFullNameLower);
      } else {
        _state.pendingSelectedRepoNames.delete(repoFullNameLower);
      }
      _renderBulkBar();
    });

    const avatar = document.createElement("img");
    avatar.src = `https://github.com/${dom.escape(owner)}.png`;
    avatar.alt = `${dom.escape(owner)} avatar`;
    avatar.width = 36;
    avatar.height = 36;
    avatar.style.cssText =
      "border-radius:8px;border:1px solid var(--border-color);flex-shrink:0;";
    avatar.onerror = () => {
      avatar.src = "https://github.com/ghost.png";
    };

    const repoMeta = document.createElement("div");

    const titleRow = document.createElement("div");
    titleRow.style.cssText =
      "display:flex;align-items:center;gap:0.5rem;flex-wrap:wrap;";

    const nameEl = document.createElement("a");
    nameEl.href = `https://github.com/${dom.escape(repo.full_name)}`;
    nameEl.target = "_blank";
    nameEl.rel = "noopener noreferrer";
    nameEl.style.cssText =
      "font-weight:700;font-size:1rem;color:var(--text-primary);text-decoration:none;";
    nameEl.textContent = dom.escape(repo.full_name);

    const visBadge = document.createElement("span");
    visBadge.className = `badge ${
      repo.private ? "badge-warning" : "badge-secondary"
    }`;
    visBadge.style.cssText = "font-size:0.65rem;";
    visBadge.textContent = repo.private ? "Private" : "Public";

    titleRow.append(nameEl, visBadge);

    const subRow = document.createElement("div");
    subRow.style.cssText =
      "font-size:0.75rem;color:var(--text-muted);margin-top:0.2rem;display:flex;gap:0.75rem;";
    subRow.textContent = `ID: ${
      repo.repo_id ?? repo.id ?? 0
    } · GitHub App Monitored`;

    repoMeta.append(titleRow, subRow);
    left.append(checkbox, avatar, repoMeta);

    const right = document.createElement("div");
    right.style.cssText = "display:flex;align-items:center;gap:1rem;";

    const statusBadge = document.createElement("span");
    statusBadge.className = `badge ${
      isEnabled ? "badge-success" : "badge-secondary"
    }`;
    statusBadge.textContent = isEnabled
      ? "AI Coverage Active"
      : "AI Review Disabled";

    right.appendChild(statusBadge);
    card.append(left, right);
    listWrapper.appendChild(card);
  });

  container.appendChild(listWrapper);
}

/**
 * 5. Pagination Controls
 */
function _renderPagination() {
  const container = document.getElementById("repos-pagination-container");
  if (!container) return;

  container.innerHTML = "";
  const filteredRepos = _getFilteredRepos();
  const totalCount = filteredRepos.length;

  if (totalCount === 0) return;

  const totalPages = Math.ceil(totalCount / _state.pageSize);

  const card = document.createElement("div");
  card.className = "glass-card";
  card.style.cssText =
    "padding:0.75rem 1.25rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem;";

  const info = document.createElement("div");
  info.style.cssText = "font-size:0.85rem;color:var(--text-secondary);";
  const start = (_state.currentPage - 1) * _state.pageSize + 1;
  const end = Math.min(_state.currentPage * _state.pageSize, totalCount);
  info.textContent = `Showing ${start}–${end} of ${totalCount} repositories`;

  const controls = document.createElement("div");
  controls.style.cssText = "display:flex;align-items:center;gap:0.5rem;";

  // Page Size Select
  const pageSizeSelect = document.createElement("select");
  pageSizeSelect.className = "form-select";
  pageSizeSelect.style.cssText = "padding:0.25rem 0.5rem;font-size:0.8rem;";
  pageSizeSelect.setAttribute("aria-label", "Repositories per page");
  [10, 25, 50, 100].forEach((size) => {
    const option = document.createElement("option");
    option.value = String(size);
    option.selected = _state.pageSize === size;
    option.textContent = `${size} / page`;
    pageSizeSelect.appendChild(option);
  });
  pageSizeSelect.addEventListener("change", (e) => {
    _state.pageSize = Number(e.target.value);
    _state.currentPage = 1;
    _renderRepoList();
    _renderPagination();
  });

  // Prev Button
  const prevBtn = document.createElement("button");
  prevBtn.type = "button";
  prevBtn.className = "btn btn-secondary";
  prevBtn.disabled = _state.currentPage === 1;
  prevBtn.style.cssText = "padding:0.3rem 0.6rem;font-size:0.8rem;";
  prevBtn.textContent = "Previous";
  prevBtn.addEventListener("click", () => {
    if (_state.currentPage > 1) {
      _state.currentPage--;
      _renderRepoList();
      _renderPagination();
      _renderBulkBar();
    }
  });

  // Next Button
  const nextBtn = document.createElement("button");
  nextBtn.type = "button";
  nextBtn.className = "btn btn-secondary";
  nextBtn.disabled = _state.currentPage >= totalPages;
  nextBtn.style.cssText = "padding:0.3rem 0.6rem;font-size:0.8rem;";
  nextBtn.textContent = "Next";
  nextBtn.addEventListener("click", () => {
    if (_state.currentPage < totalPages) {
      _state.currentPage++;
      _renderRepoList();
      _renderPagination();
      _renderBulkBar();
    }
  });

  controls.append(pageSizeSelect, prevBtn, nextBtn);
  card.append(info, controls);
  container.appendChild(card);
}

// ---------------------------------------------------------------------------
// Helpers & Actions
// ---------------------------------------------------------------------------

function _getFilteredRepos() {
  return _state.repos
    .filter((r) => {
      // Search
      if (_state.searchQuery) {
        const q = _state.searchQuery.toLowerCase();
        if (!r.full_name.toLowerCase().includes(q)) return false;
      }

      // Visibility
      if (_state.filterVisibility === "public" && r.private) return false;
      if (_state.filterVisibility === "private" && !r.private) return false;

      // Selection
      const isEnabled = _state.pendingSelectedRepoNames.has(
        r.full_name.toLowerCase()
      );
      if (_state.filterSelection === "selected" && !isEnabled) return false;
      if (_state.filterSelection === "unselected" && isEnabled) return false;

      return true;
    })
    .sort((a, b) => {
      if (_state.sortBy === "name") {
        return a.full_name.localeCompare(b.full_name);
      }
      return 0;
    });
}

function _getPaginatedRepos(filtered) {
  const start = (_state.currentPage - 1) * _state.pageSize;
  return filtered.slice(start, start + _state.pageSize);
}

function _hasUnsavedChanges() {
  if (
    _state.pendingSelectedRepoNames.size !==
    _state.initialSelectedRepoNames.size
  )
    return true;
  for (const name of _state.pendingSelectedRepoNames) {
    if (!_state.initialSelectedRepoNames.has(name)) return true;
  }
  return false;
}

async function _saveRepoSelections() {
  if (!_state.selectedInstallationId) return;

  _state.isSaving = true;
  _renderBulkBar();

  const selectedRepoFullNames = Array.from(_state.pendingSelectedRepoNames);

  try {
    await api.selectRepos(_state.selectedInstallationId, selectedRepoFullNames);
    Toast.success("Repository selections saved successfully.");
    _state.initialSelectedRepoNames = new Set(_state.pendingSelectedRepoNames);
  } catch (err) {
    console.error("[Repos] Save failed:", err);
    Toast.error(err?.message || "Failed to save repository selections.");
  } finally {
    _state.isSaving = false;
    _renderBulkBar();
    _renderRepoList();
  }
}
