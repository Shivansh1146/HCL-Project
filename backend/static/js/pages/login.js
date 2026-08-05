/**
 * pages/login.js — Enterprise Login Page.
 *
 * Design:
 *  - Full-viewport glassmorphism layout with animated gradient orbs
 *  - GitHub OAuth button (primary action)
 *  - Loading state during redirect initiation
 *  - Error state with retry
 *  - Security notice
 *
 * Security:
 *  - No tokens or secrets handled here
 *  - GitHub redirect handled entirely by authService.initiateGitHubLogin()
 *  - No user input rendered into innerHTML
 */

import { authService } from "../services/auth.js";
import { store }       from "../utils/state.js";
import { CONFIG }      from "../config/config.js";
import { dom }         from "../utils/dom.js";

// ---------------------------------------------------------------------------
// Login page CSS — injected once if not already present
// ---------------------------------------------------------------------------

const LOGIN_CSS_ID = "login-page-styles";

function injectLoginStyles() {
    if (document.getElementById(LOGIN_CSS_ID)) return;
    const style = document.createElement("style");
    style.id = LOGIN_CSS_ID;
    style.textContent = `
        .login-page {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
            position: relative;
            overflow: hidden;
        }

        /* Animated background orbs */
        .login-orb {
            position: absolute;
            border-radius: 50%;
            filter: blur(80px);
            pointer-events: none;
            animation: orbFloat 8s ease-in-out infinite;
        }
        .login-orb-1 {
            width: 500px; height: 500px;
            background: radial-gradient(circle, rgba(59,130,246,0.18) 0%, transparent 70%);
            top: -15%; left: -10%;
            animation-delay: 0s;
        }
        .login-orb-2 {
            width: 400px; height: 400px;
            background: radial-gradient(circle, rgba(168,85,247,0.14) 0%, transparent 70%);
            bottom: -10%; right: -10%;
            animation-delay: -4s;
        }
        .login-orb-3 {
            width: 300px; height: 300px;
            background: radial-gradient(circle, rgba(16,185,129,0.08) 0%, transparent 70%);
            top: 50%; left: 55%;
            animation-delay: -2s;
        }

        @keyframes orbFloat {
            0%, 100% { transform: translate(0, 0) scale(1); }
            33%       { transform: translate(20px, -30px) scale(1.04); }
            66%       { transform: translate(-15px, 20px) scale(0.97); }
        }

        /* Card */
        .login-card {
            position: relative;
            z-index: 1;
            width: 100%;
            max-width: 440px;
            background: rgba(13, 16, 23, 0.85);
            backdrop-filter: blur(24px);
            -webkit-backdrop-filter: blur(24px);
            border: 1px solid rgba(56, 62, 71, 0.6);
            border-radius: 20px;
            padding: 2.75rem 2.5rem;
            box-shadow:
                0 0 0 1px rgba(255,255,255,0.03) inset,
                0 25px 50px -12px rgba(0,0,0,0.5);
            animation: loginCardIn 0.6s cubic-bezier(0.4, 0, 0.2, 1) both;
        }

        @keyframes loginCardIn {
            from { opacity: 0; transform: translateY(24px) scale(0.97); }
            to   { opacity: 1; transform: translateY(0)    scale(1);    }
        }

        /* Logo */
        .login-logo {
            width: 52px; height: 52px;
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            border-radius: 14px;
            display: flex; align-items: center; justify-content: center;
            margin: 0 auto 1.5rem;
            box-shadow: 0 8px 24px rgba(59,130,246,0.35);
        }

        /* GitHub button */
        .btn-github-login {
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.75rem;
            padding: 0.9rem 1.5rem;
            background: #24292e;
            color: #fff;
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 10px;
            font-size: 1rem;
            font-weight: 600;
            font-family: var(--font-sans);
            cursor: pointer;
            transition: all 0.2s ease;
            position: relative;
            overflow: hidden;
        }

        .btn-github-login::before {
            content: '';
            position: absolute; inset: 0;
            background: linear-gradient(135deg, rgba(255,255,255,0.06) 0%, transparent 100%);
            opacity: 0;
            transition: opacity 0.2s ease;
        }

        .btn-github-login:hover:not(:disabled) {
            background: #1b1f23;
            border-color: rgba(255,255,255,0.25);
            transform: translateY(-1px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.4);
        }
        .btn-github-login:hover:not(:disabled)::before { opacity: 1; }

        .btn-github-login:active:not(:disabled) {
            transform: translateY(0);
            box-shadow: none;
        }

        .btn-github-login:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }

        /* Feature list */
        .feature-list {
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 0.6rem;
            margin: 1.5rem 0;
        }

        .feature-item {
            display: flex;
            align-items: center;
            gap: 0.65rem;
            font-size: 0.88rem;
            color: var(--text-secondary);
        }

        .feature-icon {
            width: 20px; height: 20px;
            border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            flex-shrink: 0;
        }

        /* Error state */
        .login-error-box {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.25);
            border-radius: 10px;
            padding: 0.85rem 1rem;
            display: flex;
            align-items: flex-start;
            gap: 0.65rem;
            margin-bottom: 1.25rem;
            animation: fadeIn 0.3s ease;
        }

        /* Security notice */
        .security-notice {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.4rem;
            margin-top: 1.5rem;
            font-size: 0.78rem;
            color: var(--text-muted);
        }

        /* Divider */
        .login-divider {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin: 1.5rem 0;
            color: var(--text-muted);
            font-size: 0.8rem;
        }
        .login-divider::before,
        .login-divider::after {
            content: '';
            flex: 1;
            height: 1px;
            background: var(--border-color);
        }

        @media (prefers-reduced-motion: reduce) {
            .login-orb { animation: none; }
            .login-card { animation: none; }
        }
    `;
    document.head.appendChild(style);
}

// ---------------------------------------------------------------------------
// Render Function
// ---------------------------------------------------------------------------

/**
 * Renders the enterprise login page into the given outlet element.
 * @param {HTMLElement} outlet
 */
export async function renderLoginPage(outlet) {
    injectLoginStyles();

    // If already authenticated, redirect to dashboard immediately
    if (store.getState().isAuthenticated) {
        const returnTo = authService.consumeReturnTo();
        window.location.hash = returnTo;
        return;
    }

    // Check if we arrived here after a failed callback (query param)
    const urlParams = new URLSearchParams(window.location.search);
    const oauthError = urlParams.get("error");
    const errorDesc  = urlParams.get("error_description");

    // -----------------------------------------------------------------------
    // Build the page structure via DOM API (no user data in innerHTML)
    // -----------------------------------------------------------------------
    outlet.innerHTML = "";
    outlet.style.cssText = "padding:0;max-width:100%;";

    const page = document.createElement("div");
    page.className = "login-page";

    // Background orbs (decorative, no user content)
    [1, 2, 3].forEach(n => {
        const orb = document.createElement("div");
        orb.className = `login-orb login-orb-${n}`;
        orb.setAttribute("aria-hidden", "true");
        page.appendChild(orb);
    });

    // Card
    const card = document.createElement("div");
    card.className = "login-card";
    card.setAttribute("role", "main");

    // Logo
    const logo = document.createElement("div");
    logo.className = "login-logo";
    logo.setAttribute("aria-hidden", "true");
    logo.innerHTML = `<svg width="26" height="26" viewBox="0 0 24 24" fill="white"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/></svg>`;

    // Heading
    const heading = document.createElement("div");
    heading.style.cssText = "text-align:center;margin-bottom:1.75rem;";
    heading.innerHTML = `
        <h1 style="font-size:1.6rem;font-weight:800;letter-spacing:-0.03em;margin-bottom:0.4rem;
                   background:linear-gradient(to right,#fff,#94a3b8);-webkit-background-clip:text;
                   background-clip:text;-webkit-text-fill-color:transparent;">
            AI Code Reviewer
        </h1>
        <p style="font-size:0.9rem;color:var(--text-secondary);line-height:1.6;">
            Enterprise GitHub Pull Request Analysis,<br>powered by Groq AI
        </p>
    `;

    // Error box (if OAuth error in URL)
    let errorBox = null;
    if (oauthError) {
        errorBox = document.createElement("div");
        errorBox.className = "login-error-box";
        errorBox.setAttribute("role", "alert");

        const iconEl = document.createElement("span");
        iconEl.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;

        const msgEl = document.createElement("div");
        const titleEl = document.createElement("p");
        titleEl.style.cssText = "font-size:0.85rem;font-weight:600;color:#ef4444;margin-bottom:0.2rem;";
        titleEl.textContent = "Authentication Failed";  // static

        const descEl = document.createElement("p");
        descEl.style.cssText = "font-size:0.8rem;color:var(--text-secondary);";
        // XSS-safe: errorDesc is URL param — escape before displaying
        descEl.textContent = errorDesc
            ? decodeURIComponent(errorDesc).slice(0, 200)
            : "GitHub OAuth failed. Please try again.";

        msgEl.append(titleEl, descEl);
        errorBox.append(iconEl, msgEl);
    }

    // Feature list (static)
    const features = document.createElement("ul");
    features.className = "feature-list";
    features.setAttribute("aria-label", "Platform features");

    const FEATURES = [
        { icon: "#10b981", svg: `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>`, label: "Automated AI code review on every PR" },
        { icon: "#3b82f6", svg: `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>`, label: "Security, performance & quality analysis" },
        { icon: "#a855f7", svg: `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>`, label: "Multi-organization repository management" },
    ];

    FEATURES.forEach(f => {
        const li    = document.createElement("li");
        li.className = "feature-item";

        const iconWrap = document.createElement("div");
        iconWrap.className  = "feature-icon";
        iconWrap.style.background = f.icon;
        iconWrap.setAttribute("aria-hidden", "true");
        iconWrap.innerHTML  = f.svg;  // static, not user data

        const labelEl = document.createElement("span");
        labelEl.textContent = f.label;  // static strings, textContent still safer

        li.append(iconWrap, labelEl);
        features.appendChild(li);
    });

    // Divider
    const divider = document.createElement("div");
    divider.className = "login-divider";
    divider.setAttribute("aria-hidden", "true");
    divider.textContent = "Continue with";

    // GitHub button
    const githubBtn = document.createElement("button");
    githubBtn.type = "button";
    githubBtn.id   = "login-github-btn";
    githubBtn.className = "btn-github-login";
    githubBtn.setAttribute("aria-label", "Sign in with GitHub");

    const githubIcon = document.createElement("span");
    githubIcon.setAttribute("aria-hidden", "true");
    githubIcon.innerHTML = `<svg height="22" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>`;

    const btnText = document.createElement("span");
    btnText.id = "login-btn-text";
    btnText.textContent = "Continue with GitHub";

    const spinner = document.createElement("span");
    spinner.id    = "login-spinner";
    spinner.style.display = "none";
    spinner.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="animation:spin 0.7s linear infinite" aria-hidden="true"><path d="M12 2a10 10 0 0 1 10 10"/></svg>`;

    githubBtn.append(githubIcon, spinner, btnText);

    // Wire click handler
    githubBtn.addEventListener("click", () => _handleLoginClick(githubBtn, btnText, spinner));

    // Security notice (static)
    const securityNotice = document.createElement("div");
    securityNotice.className = "security-notice";
    securityNotice.innerHTML = `
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        <span>Secured by GitHub OAuth 2.0 · No passwords stored</span>
    `;

    // Assemble card
    card.append(logo, heading);
    if (errorBox) card.appendChild(errorBox);
    card.append(features, divider, githubBtn, securityNotice);

    page.appendChild(card);
    outlet.appendChild(page);

    // Focus the login button for keyboard users
    githubBtn.focus();
}

// ---------------------------------------------------------------------------
// Login click handler (extracted for testability)
// ---------------------------------------------------------------------------

async function _handleLoginClick(btn, textEl, spinnerEl) {
    // Show loading state
    btn.disabled      = true;
    textEl.textContent = "Redirecting to GitHub…";
    spinnerEl.style.display = "inline-flex";

    try {
        // Preserve current route as return destination
        const returnTo = window.location.hash &&
            window.location.hash !== CONFIG.ROUTES.LOGIN
                ? window.location.hash
                : CONFIG.ROUTES.DASHBOARD;

        await authService.initiateGitHubLogin(returnTo);
        // Page will navigate away — no further UI updates needed
    } catch (err) {
        // Restore button state on error
        btn.disabled       = false;
        textEl.textContent  = "Continue with GitHub";
        spinnerEl.style.display = "none";

        // Show inline error
        _showInlineError(btn.closest(".login-card"), err?.message || "Failed to initiate login. Please try again.");
    }
}

function _showInlineError(card, message) {
    // Remove any existing error box
    card?.querySelector(".login-error-box")?.remove();

    const errorBox = document.createElement("div");
    errorBox.className = "login-error-box";
    errorBox.setAttribute("role", "alert");
    errorBox.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;

    const msgEl = document.createElement("span");
    msgEl.style.cssText = "font-size:0.85rem;color:var(--text-secondary);";
    msgEl.textContent = message;  // safe: textContent
    errorBox.appendChild(msgEl);

    // Insert before the GitHub button
    const githubBtn = card?.querySelector("#login-github-btn");
    if (githubBtn) githubBtn.insertAdjacentElement("beforebegin", errorBox);

    errorBox.querySelector?.("button")?.focus();
}
