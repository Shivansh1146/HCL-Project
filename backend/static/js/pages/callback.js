/**
 * pages/callback.js — OAuth Callback Handler Page.
 *
 * The backend handles the actual OAuth exchange at GET /auth/callback
 * and then redirects to "/" with the session cookie set.
 *
 * This page handles the case where the backend redirects to "/#/callback"
 * (if configured to do so), or where the app simply boots at "/" after
 * the cookie has already been set.
 *
 * The primary job here is:
 *  1. Show a loading splash while session is being verified
 *  2. Restore the session via GET /auth/me
 *  3. Navigate to the saved return URL
 *  4. If session fails, redirect to login with error
 */

import { authService } from "../services/auth.js";
import { CONFIG }      from "../config/config.js";

/**
 * Renders a loading splash and completes the post-OAuth session handshake.
 * @param {HTMLElement} outlet
 */
export async function renderCallbackPage(outlet) {
    outlet.innerHTML = `
        <div style="
            display:flex; flex-direction:column; align-items:center;
            justify-content:center; height:70vh; gap:1.25rem; text-align:center;
        ">
            <div style="
                width:52px;height:52px;
                background:linear-gradient(135deg,#3b82f6,#8b5cf6);
                border-radius:14px;display:flex;align-items:center;justify-content:center;
                box-shadow:0 8px 24px rgba(59,130,246,0.35);
                animation:pulse 1.5s ease infinite;
            " aria-hidden="true">
                <svg width="26" height="26" viewBox="0 0 24 24" fill="white">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/>
                </svg>
            </div>
            <div>
                <h2 style="font-size:1.1rem;font-weight:700;margin-bottom:0.4rem;">Completing sign-in…</h2>
                <p style="font-size:0.9rem;color:var(--text-muted);">Verifying your GitHub session</p>
            </div>
            <div class="spinner" aria-label="Loading"></div>
        </div>
    `;

    try {
        const restored = await authService.restoreSession();
        if (restored) {
            const returnTo = authService.consumeReturnTo();
            window.location.hash = returnTo;
        } else {
            window.location.hash = `${CONFIG.ROUTES.LOGIN}?error=session_failed`;
        }
    } catch {
        window.location.hash = CONFIG.ROUTES.LOGIN;
    }
}
