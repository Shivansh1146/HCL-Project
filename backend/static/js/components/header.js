/**
 * header.js — Enterprise Header / Top Navigation Component.
 *
 * Responsibilities:
 *  - Mobile menu toggle
 *  - Breadcrumb navigation display
 *  - Organization Switcher dropdown
 *  - Theme Toggle button (Dark / Light mode)
 *  - Notification Bell icon with active badge placeholder
 *  - User Avatar & Quick Menu
 */

import { store } from "../utils/state.js";
import { dom }   from "../utils/dom.js";
import { Toast } from "./toast.js";

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

    // Mobile Hamburger Toggle
    const mobileBtn = document.createElement("button");
    mobileBtn.type = "button";
    mobileBtn.className = "icon-btn mobile-only";
    mobileBtn.setAttribute("aria-label", "Toggle navigation menu");
    mobileBtn.style.cssText = "display:none;"; // Visible only on mobile via media query/flex
    mobileBtn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>`;
    mobileBtn.addEventListener("click", () => {
        const sidebar = document.getElementById("sidebar");
        const backdrop = document.getElementById("sidebar-backdrop");
        sidebar?.classList.toggle("mobile-open");
        backdrop?.classList.toggle("active");
    });

    // Breadcrumb Container
    const breadcrumbs = document.createElement("div");
    breadcrumbs.id = "page-breadcrumb";
    breadcrumbs.style.cssText = "display:flex;align-items:center;gap:0.5rem;font-size:0.9rem;font-weight:500;color:var(--text-secondary);";

    leftSection.append(mobileBtn, breadcrumbs);

    // --- Right Section: Org Switcher, Theme Toggle, Notification Bell, User Avatar ---
    const rightSection = document.createElement("div");
    rightSection.className = "header-actions-group";

    // 1. Organization Switcher Dropdown
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

    const orgList = ["Personal", ...(orgs.filter(o => o !== "Personal"))];
    orgList.forEach(orgName => {
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

    // 2. Notification Bell (Placeholder)
    const notifBtn = document.createElement("button");
    notifBtn.type = "button";
    notifBtn.className = "icon-btn";
    notifBtn.setAttribute("aria-label", "Notifications");
    notifBtn.setAttribute("data-tooltip", "Notifications");
    notifBtn.innerHTML = `
        <div style="position:relative;display:flex;align-items:center;justify-content:center;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg>
            <span style="position:absolute;top:-4px;right:-4px;width:7px;height:7px;background:var(--primary);border-radius:50%;"></span>
        </div>
    `;
    notifBtn.addEventListener("click", () => {
        Toast.info("No unread notifications.");
    });

    // 4. User Avatar Quick Link
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
        rightSection.append(orgWrap, notifBtn, avatarLink);
    } else {
        rightSection.append(orgWrap, notifBtn);
    }

    headerEl.append(leftSection, rightSection);
}
