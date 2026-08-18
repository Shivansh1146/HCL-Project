/**
 * header.js — Enterprise Header / Top Navigation Component.
 *
 * Responsibilities:
 *  - Mobile menu toggle
 *  - Breadcrumb navigation display
 *  - Organization Switcher dropdown
 *  - Theme Toggle button (Dark / Light mode)
 *  - Notification Bell icon with live unread count + dropdown
 *  - User Avatar & Quick Menu
 */

import { store } from "../utils/state.js";
import { dom }   from "../utils/dom.js";
import { Toast } from "./toast.js";
import { api }   from "../services/api.js";

// ---------------------------------------------------------------------------
// Module-level notification state (survives re-renders within a page session)
// ---------------------------------------------------------------------------
let _notifData    = [];    // latest fetched notifications
let _notifTimer   = null;  // polling timer ID
let _notifOpen    = false; // dropdown open state
let _notifBtnRef  = null;  // reference to the bell button for badge updates
let _notifPanelRef = null; // reference to the dropdown panel

/**
 * Fetch notifications from backend and update bell badge.
 * Never throws — errors are swallowed so the header never crashes.
 */
async function _fetchAndUpdateNotifications() {
    try {
        const data = await api.getNotifications();
        _notifData = Array.isArray(data) ? data
            : (Array.isArray(data?.notifications) ? data.notifications : []);
        _updateBellBadge();
        if (_notifOpen && _notifPanelRef) {
            _renderNotificationList(_notifPanelRef);
        }
    } catch (_) {
        // silent — user may not be authenticated yet
    }
}

/** Updates the unread count badge on the bell button. */
function _updateBellBadge() {
    if (!_notifBtnRef) return;
    const unreadCount = _notifData.filter(n => !n.is_read).length;
    const badge = _notifBtnRef.querySelector(".notif-badge");
    if (!badge) return;
    if (unreadCount > 0) {
        badge.textContent = unreadCount > 99 ? "99+" : String(unreadCount);
        badge.style.display = "flex";
    } else {
        badge.style.display = "none";
    }
}

/** Renders the notification list inside the dropdown panel. */
function _renderNotificationList(panel) {
    const list = panel.querySelector(".notif-list");
    if (!list) return;
    list.innerHTML = "";

    if (_notifData.length === 0) {
        const empty = document.createElement("div");
        empty.style.cssText = "padding:1.5rem;text-align:center;color:var(--text-secondary);font-size:0.85rem;";
        empty.textContent = "No notifications yet.";
        list.appendChild(empty);
        return;
    }

    _notifData.forEach(n => {
        const item = document.createElement("div");
        item.className = "notif-item";
        item.style.cssText = [
            "padding:0.75rem 1rem",
            "border-bottom:1px solid var(--border-color)",
            "cursor:pointer",
            "transition:background 0.15s",
            `background:${n.is_read ? "transparent" : "rgba(var(--primary-rgb,99,102,241),0.06)"}`,
        ].join(";");
        item.setAttribute("data-notif-id", n.id);

        const titleEl = document.createElement("div");
        titleEl.style.cssText = `font-size:0.85rem;font-weight:${n.is_read ? "400" : "600"};color:var(--text-primary);margin-bottom:0.2rem;`;
        titleEl.textContent = dom.escape(n.title || "Notification");

        const msgEl = document.createElement("div");
        msgEl.style.cssText = "font-size:0.78rem;color:var(--text-secondary);margin-bottom:0.25rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:260px;";
        msgEl.textContent = dom.escape(n.message || "");

        const timeEl = document.createElement("div");
        timeEl.style.cssText = "font-size:0.72rem;color:var(--text-secondary);opacity:0.7;";
        try { timeEl.textContent = new Date(n.created_at).toLocaleString(); }
        catch (_) { timeEl.textContent = n.created_at || ""; }

        item.append(titleEl, msgEl, timeEl);

        item.addEventListener("mouseenter", () => {
            item.style.background = "var(--hover-bg, rgba(255,255,255,0.05))";
        });
        item.addEventListener("mouseleave", () => {
            item.style.background = n.is_read ? "transparent" : "rgba(var(--primary-rgb,99,102,241),0.06)";
        });

        item.addEventListener("click", async () => {
            if (!n.is_read) {
                try {
                    await api.markNotificationRead(n.id);
                    n.is_read = 1;
                    titleEl.style.fontWeight = "400";
                    item.style.background = "transparent";
                    _updateBellBadge();
                } catch (_) { /* silent */ }
            }
            if (n.link) {
                window.location.hash = n.link.replace(/^#/, "");
            }
        });

        list.appendChild(item);
    });
}

/**
 * Renders the header content into the top header container.
 * @param {HTMLElement} headerEl
 */
export function renderHeader(headerEl) {
    if (!headerEl) return;

    const state = store.getState();
    const user = state.user;
    const currentOrg = state.currentOrg || "Personal";
    const orgs = state.organizations || ["Personal"];

    headerEl.innerHTML = "";

    // --- Left Section: Mobile Toggle & Breadcrumbs ---
    const leftSection = document.createElement("div");
    leftSection.style.cssText = "display:flex;align-items:center;gap:0.75rem;";

    const mobileBtn = document.createElement("button");
    mobileBtn.type = "button";
    mobileBtn.className = "icon-btn mobile-only";
    mobileBtn.setAttribute("aria-label", "Toggle navigation menu");
    mobileBtn.style.cssText = "display:none;";
    mobileBtn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>`;
    mobileBtn.addEventListener("click", () => {
        const sidebar = document.getElementById("sidebar");
        const backdrop = document.getElementById("sidebar-backdrop");
        sidebar?.classList.toggle("mobile-open");
        backdrop?.classList.toggle("active");
    });

    const breadcrumbs = document.createElement("div");
    breadcrumbs.id = "page-breadcrumb";
    breadcrumbs.style.cssText = "display:flex;align-items:center;gap:0.5rem;font-size:0.9rem;font-weight:500;color:var(--text-secondary);";

    leftSection.append(mobileBtn, breadcrumbs);

    // --- Right Section ---
    const rightSection = document.createElement("div");
    rightSection.className = "header-actions-group";

    // 1. Organization Switcher
    const orgWrap = document.createElement("div");
    orgWrap.style.cssText = "position:relative;";

    const orgBtn = document.createElement("button");
    orgBtn.type = "button";
    orgBtn.className = "org-switcher";
    orgBtn.id = "org-switcher-btn";
    orgBtn.setAttribute("aria-haspopup", "true");
    orgBtn.setAttribute("aria-expanded", "false");
    orgBtn.setAttribute("aria-label", "Switch organization");
    orgBtn.innerHTML = `
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>
        <span>${dom.escape(currentOrg)}</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>
    `;

    const orgMenu = document.createElement("div");
    orgMenu.className = "glass-card";
    orgMenu.style.cssText = "display:none;position:absolute;top:calc(100% + 8px);right:0;width:200px;padding:0.5rem;z-index:200;box-shadow:var(--shadow-lg);";
    orgMenu.setAttribute("role", "menu");

    ["Personal", ...(orgs.filter(o => o !== "Personal"))].forEach(orgName => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = `sidebar-nav-link ${orgName === currentOrg ? "active" : ""}`;
        item.style.cssText = "width:100%;text-align:left;font-size:0.85rem;padding:0.5rem 0.75rem;";
        item.setAttribute("role", "menuitem");
        item.textContent = dom.escape(orgName);
        item.addEventListener("click", () => {
            store.setCurrentOrg(orgName);
            Toast.info(`Switched to organization: ${orgName}`);
            orgMenu.style.display = "none";
            orgBtn.setAttribute("aria-expanded", "false");
        });
        orgMenu.appendChild(item);
    });

    orgBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const isExpanded = orgMenu.style.display === "block";
        orgMenu.style.display = isExpanded ? "none" : "block";
        orgBtn.setAttribute("aria-expanded", String(!isExpanded));
    });

    document.addEventListener("click", (e) => {
        if (!orgWrap.contains(e.target)) {
            orgMenu.style.display = "none";
            orgBtn.setAttribute("aria-expanded", "false");
        }
    });

    orgWrap.append(orgBtn, orgMenu);

    // 2. Notification Bell (Live)
    const notifWrap = document.createElement("div");
    notifWrap.style.cssText = "position:relative;";

    const notifBtn = document.createElement("button");
    notifBtn.type = "button";
    notifBtn.className = "icon-btn";
    notifBtn.id = "notification-bell-btn";
    notifBtn.setAttribute("aria-label", "Notifications");
    notifBtn.setAttribute("data-tooltip", "Notifications");
    notifBtn.innerHTML = `
        <div style="position:relative;display:flex;align-items:center;justify-content:center;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                <path d="M13.73 21a2 2 0 01-3.46 0"/>
            </svg>
            <span class="notif-badge" style="
                display:none;position:absolute;top:-6px;right:-8px;
                min-width:16px;height:16px;padding:0 3px;
                background:#ef4444;color:#fff;
                border-radius:8px;font-size:0.65rem;font-weight:700;
                align-items:center;justify-content:center;
                border:2px solid var(--bg-primary,#0f172a);
                line-height:1;
            "></span>
        </div>
    `;

    // Notification Dropdown Panel
    const notifPanel = document.createElement("div");
    notifPanel.className = "glass-card";
    notifPanel.id = "notification-panel";
    notifPanel.style.cssText = [
        "display:none",
        "position:absolute",
        "top:calc(100% + 10px)",
        "right:0",
        "width:320px",
        "max-height:420px",
        "overflow-y:auto",
        "z-index:300",
        "box-shadow:var(--shadow-lg)",
        "border-radius:12px",
        "font-family:inherit",
    ].join(";");
    notifPanel.setAttribute("role", "dialog");
    notifPanel.setAttribute("aria-label", "Notifications panel");

    // Panel header row
    const panelHeader = document.createElement("div");
    panelHeader.style.cssText = "display:flex;align-items:center;justify-content:space-between;padding:0.75rem 1rem;border-bottom:1px solid var(--border-color);";

    const panelTitle = document.createElement("span");
    panelTitle.style.cssText = "font-size:0.875rem;font-weight:600;color:var(--text-primary);";
    panelTitle.textContent = "Notifications";

    const markAllBtn = document.createElement("button");
    markAllBtn.type = "button";
    markAllBtn.style.cssText = "font-size:0.75rem;color:var(--primary);background:none;border:none;cursor:pointer;padding:0;";
    markAllBtn.textContent = "Mark all read";
    markAllBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        try {
            await api.markAllNotificationsRead();
            _notifData.forEach(n => { n.is_read = 1; });
            _renderNotificationList(notifPanel);
            _updateBellBadge();
        } catch (_) { /* silent */ }
    });

    panelHeader.append(panelTitle, markAllBtn);

    const notifList = document.createElement("div");
    notifList.className = "notif-list";

    notifPanel.append(panelHeader, notifList);

    // Toggle dropdown
    notifBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        _notifOpen = !_notifOpen;
        notifPanel.style.display = _notifOpen ? "block" : "none";
        if (_notifOpen) _renderNotificationList(notifPanel);
    });

    // Close on outside click
    document.addEventListener("click", (e) => {
        if (!notifWrap.contains(e.target)) {
            _notifOpen = false;
            notifPanel.style.display = "none";
        }
    });

    notifWrap.append(notifBtn, notifPanel);

    // Store module-level refs for badge updates across polls
    _notifBtnRef   = notifBtn;
    _notifPanelRef = notifPanel;

    // Start 30s polling (only one timer)
    if (_notifTimer) clearInterval(_notifTimer);
    _notifTimer = setInterval(_fetchAndUpdateNotifications, 30000);

    // Immediate fetch on render
    _fetchAndUpdateNotifications();

    // 3. User Avatar
    if (user) {
        const avatarLink = document.createElement("a");
        avatarLink.href = "#/profile";
        avatarLink.setAttribute("aria-label", "View Profile");
        avatarLink.setAttribute("data-tooltip", `@${dom.escape(user.login)}`);
        avatarLink.style.cssText = "display:flex;align-items:center;";

        const img = document.createElement("img");
        img.src = dom.safeUrl(user.avatar_url || "");
        img.alt = `${dom.escape(user.login)} avatar`;
        img.width = 34;
        img.height = 34;
        img.style.cssText = "border-radius:50%;border:2px solid var(--border-color);transition:var(--transition-fast);";
        img.onerror = () => { img.src = "https://github.com/ghost.png"; };

        avatarLink.appendChild(img);
        rightSection.append(orgWrap, notifWrap, avatarLink);
    } else {
        rightSection.append(orgWrap, notifWrap);
    }

    headerEl.append(leftSection, rightSection);
}
