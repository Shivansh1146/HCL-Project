/**
 * sidebar.js — Accessible, Collapsible Enterprise Sidebar Navigation Component.
 *
 * Requirements:
 *  - Project Logo & App Title
 *  - Collapse / Expand Toggle
 *  - Navigation links: Dashboard, Repositories, Organizations, Profile, Settings, Analytics (disabled)
 *  - Logout button
 *  - Highlight active route & ARIA keyboard accessibility
 *  - XSS safe via dom.escape() and dom.safeUrl()
 */

import { CONFIG }  from "../config/config.js";
import { store }   from "../utils/state.js";
import { api }     from "../services/api.js";
import { Toast }   from "./toast.js";
import { dom }     from "../utils/dom.js";

const NAV_ITEMS = [
    {
        href: "#/dashboard",
        label: "Dashboard",
        icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>`
    },
    {
        href: "#/repositories",
        label: "Repositories",
        icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M3 3h18v18H3zM3 9h18M9 21V9"/></svg>`
    },
    {
        href: "#/pull-requests",
        label: "Pull Requests",
        icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5"/></svg>`
    },
    {
        href: "#/organizations",
        label: "Organizations",
        icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>`
    },
    {
        href: "#/profile",
        label: "Profile",
        icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`
    },
    {
        href: "#/settings",
        label: "Settings",
        icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>`
    },
    {
        href: "#/analytics",
        label: "Analytics",
        icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`
    }
];

let _hashChangeListener = null;
let _isCollapsed = false;

/**
 * Renders the sidebar into mountEl.
 * @param {HTMLElement} mountEl
 */
export function renderSidebar(mountEl) {
    if (!mountEl) return;

    const state = store.getState();
    const user  = state.user;
    const route = window.location.hash || "#/dashboard";

    mountEl.className = `sidebar-container ${_isCollapsed ? "collapsed" : ""}`;

    // --- Header Section: Logo + Collapse Toggle ---
    const headerSection = document.createElement("div");
    headerSection.style.cssText = "display:flex;align-items:center;justify-content:space-between;margin-bottom:2rem;";

    const logoWrapper = document.createElement("div");
    logoWrapper.style.cssText = "display:flex;align-items:center;gap:0.75rem;overflow:hidden;";
    logoWrapper.innerHTML = `
        <div style="width:34px;height:34px;background:linear-gradient(135deg,#3b82f6,#8b5cf6);border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0;" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="white"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/></svg>
        </div>
        <div class="sidebar-logo-text">
            <h1 style="font-size:0.95rem;font-weight:700;letter-spacing:-0.02em;white-space:nowrap;">AI Code Reviewer</h1>
            <p style="font-size:0.7rem;color:var(--text-muted);white-space:nowrap;">SaaS Command Center</p>
        </div>
    `;

    const collapseBtn = document.createElement("button");
    collapseBtn.type = "button";
    collapseBtn.id = "sidebar-collapse-btn";
    collapseBtn.className = "icon-btn sidebar-text";
    collapseBtn.style.cssText = "width:28px;height:28px;padding:0;";
    collapseBtn.setAttribute("aria-label", _isCollapsed ? "Expand sidebar" : "Collapse sidebar");
    collapseBtn.innerHTML = _isCollapsed
        ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="13 17 18 12 13 7"/><polyline points="6 17 11 12 6 7"/></svg>`
        : `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="11 17 6 12 11 7"/><polyline points="18 17 13 12 18 7"/></svg>`;

    collapseBtn.addEventListener("click", () => {
        _isCollapsed = !_isCollapsed;
        const mainWrapper = document.querySelector(".main-wrapper");
        if (_isCollapsed) {
            mountEl.classList.add("collapsed");
            mainWrapper?.classList.add("sidebar-collapsed");
        } else {
            mountEl.classList.remove("collapsed");
            mainWrapper?.classList.remove("sidebar-collapsed");
        }
        renderSidebar(mountEl);
    });

    headerSection.append(logoWrapper, collapseBtn);

    // --- Main Nav ---
    const nav = document.createElement("nav");
    nav.setAttribute("aria-label", "Main navigation");
    nav.style.flex = "1";

    const ul = document.createElement("ul");
    ul.style.cssText = "list-style:none;display:flex;flex-direction:column;gap:0.35rem;";

    NAV_ITEMS.forEach(item => {
        const li   = document.createElement("li");
        const link = document.createElement("a");

        if (item.disabled) {
            link.href = "javascript:void(0)";
            link.className = "sidebar-nav-link disabled";
            link.style.cssText = "opacity:0.5;cursor:not-allowed;";
            link.setAttribute("aria-disabled", "true");
            link.setAttribute("tabindex", "-1");
        } else {
            link.href = item.href;
            link.className = `sidebar-nav-link ${route === item.href ? "active" : ""}`;
            link.setAttribute("aria-current", route === item.href ? "page" : "false");
        }

        if (_isCollapsed) {
            link.setAttribute("data-tooltip", item.label);
        }

        const iconSpan = document.createElement("span");
        iconSpan.innerHTML = item.icon;

        const labelSpan = document.createElement("span");
        labelSpan.className = "sidebar-text";
        labelSpan.textContent = item.label;

        link.append(iconSpan, labelSpan);

        if (item.badge) {
            const badgeSpan = document.createElement("span");
            badgeSpan.className = "badge badge-primary sidebar-badge";
            badgeSpan.style.cssText = "margin-left:auto;font-size:0.65rem;padding:0.1rem 0.4rem;";
            badgeSpan.textContent = item.badge;
            link.appendChild(badgeSpan);
        }

        li.appendChild(link);
        ul.appendChild(li);
    });

    nav.appendChild(ul);

    // --- Footer Section ---
    const footer = document.createElement("div");
    footer.style.cssText = "border-top:1px solid var(--border-color);padding-top:1rem;margin-top:auto;";

    if (user) {
        const safeLogin     = dom.escape(user.login || "");
        const safeName      = dom.escape(user.name  || user.login || "");
        const safeAvatarUrl = dom.safeUrl(user.avatar_url || "");

        const userCard = document.createElement("div");
        userCard.style.cssText = "display:flex;align-items:center;gap:0.75rem;margin-bottom:0.75rem;";

        const avatar = document.createElement("img");
        avatar.src    = safeAvatarUrl;
        avatar.alt    = `${safeLogin} avatar`;
        avatar.width  = 36;
        avatar.height = 36;
        avatar.style.cssText = "border-radius:50%;border:2px solid var(--border-color);flex-shrink:0;";
        avatar.onerror = () => { avatar.src = "https://github.com/ghost.png"; };

        const userInfo = document.createElement("div");
        userInfo.className = "sidebar-user-details";
        userInfo.style.overflow = "hidden";

        const nameEl = document.createElement("p");
        nameEl.style.cssText = "font-size:0.85rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;";
        nameEl.textContent = safeName;

        const handleEl = document.createElement("p");
        handleEl.style.cssText = "font-size:0.7rem;color:var(--text-muted);";
        handleEl.textContent = `@${safeLogin}`;

        userInfo.append(nameEl, handleEl);
        userCard.append(avatar, userInfo);

        const logoutBtn = document.createElement("button");
        logoutBtn.id   = "sidebar-logout-btn";
        logoutBtn.type = "button";
        logoutBtn.className = "btn btn-ghost sidebar-footer-btn";
        logoutBtn.style.cssText = "width:100%;justify-content:flex-start;gap:0.5rem;color:var(--text-secondary);";
        if (_isCollapsed) logoutBtn.setAttribute("data-tooltip", "Sign Out");

        logoutBtn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            <span class="sidebar-text">Sign Out</span>
        `;

        logoutBtn.addEventListener("click", async () => {
            logoutBtn.disabled = true;
            try {
                await api.logout();
                store.reset();
                window.location.hash = CONFIG.ROUTES.LOGIN;
            } catch {
                Toast.error("Failed to sign out. Please try again.");
                logoutBtn.disabled = false;
            }
        });

        footer.append(userCard, logoutBtn);
    } else {
        const loginLink = document.createElement("a");
        loginLink.href  = CONFIG.ROUTES.LOGIN;
        loginLink.className = "btn btn-github sidebar-footer-btn";
        loginLink.style.cssText = "width:100%;justify-content:center;";
        loginLink.innerHTML = `<span class="sidebar-text">Sign In with GitHub</span>`;
        footer.appendChild(loginLink);
    }

    // Assemble
    mountEl.innerHTML = "";
    mountEl.append(headerSection, nav, footer);

    // Active route listener
    if (_hashChangeListener) {
        window.removeEventListener("hashchange", _hashChangeListener);
    }
    _hashChangeListener = () => {
        const links = mountEl.querySelectorAll(".sidebar-nav-link:not(.disabled)");
        links.forEach(link => {
            const isActive = link.getAttribute("href") === window.location.hash;
            link.classList.toggle("active", isActive);
            link.setAttribute("aria-current", isActive ? "page" : "false");
        });
    };
    window.addEventListener("hashchange", _hashChangeListener);
}
