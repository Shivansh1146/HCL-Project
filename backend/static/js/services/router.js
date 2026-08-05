/**
 * router.js — Production-grade Hash-based SPA Router.
 *
 * Improvements over v1:
 *  - Single, stable hashchange listener (no leaks)
 *  - Auth guard uses store state first, only calls API if stale
 *  - Emits navigation events (before-navigate, after-navigate)
 *  - 404 and 401/Unauthorized built-in page renders
 *  - scroll-to-top on every navigation
 *  - Route metadata (title, requiresAuth)
 */

import { store }  from "../utils/state.js";
import { CONFIG } from "../config/config.js";
import { api }    from "../services/api.js";

const DEFAULT_TITLE = "AI Code Reviewer";

// ---------------------------------------------------------------------------
// Built-in Special Pages
// ---------------------------------------------------------------------------

function render404(outlet) {
    outlet.innerHTML = `
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:60vh;gap:1.25rem;text-align:center;">
            <div style="font-size:5rem;font-weight:900;opacity:0.08;letter-spacing:-0.05em;">404</div>
            <h2 style="font-size:1.4rem;font-weight:700;">Page Not Found</h2>
            <p style="color:var(--text-muted);font-size:0.95rem;">The page you are looking for does not exist.</p>
            <a href="${CONFIG.ROUTES.DASHBOARD}" class="btn btn-primary">Go to Dashboard</a>
        </div>
    `;
}

function render401(outlet) {
    outlet.innerHTML = `
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:60vh;gap:1.25rem;text-align:center;">
            <div style="font-size:5rem;font-weight:900;opacity:0.08;letter-spacing:-0.05em;">401</div>
            <h2 style="font-size:1.4rem;font-weight:700;">Access Denied</h2>
            <p style="color:var(--text-muted);font-size:0.95rem;">You must be signed in to view this page.</p>
            <a href="${CONFIG.ROUTES.LOGIN}" class="btn btn-github">Sign in with GitHub</a>
        </div>
    `;
}

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------

class Router {
    constructor() {
        /** @type {Map<string, {render: Function, title: string, requiresAuth: boolean}>} */
        this._routes      = new Map();
        this._outlet      = null;
        this._currentHash = null;
        this._navigating  = false;

        // Single stable listener — bound once in start()
        this._onHashChange = () => this._navigate();
    }

    /**
     * @param {string}   hash          Route hash, e.g. "#/dashboard"
     * @param {Function} renderFn      async (outlet: HTMLElement) => void
     * @param {object}   [meta]
     * @param {string}   [meta.title]        Page title
     * @param {boolean}  [meta.requiresAuth] Defaults to true
     */
    register(hash, renderFn, meta = {}) {
        this._routes.set(hash, {
            render:      renderFn,
            title:       meta.title || DEFAULT_TITLE,
            requiresAuth: meta.requiresAuth !== false   // default: protected
        });
        return this;  // fluent chaining
    }

    setOutlet(el) {
        this._outlet = el;
        return this;
    }

    start() {
        window.addEventListener("hashchange", this._onHashChange);
        return this._navigate();  // Handle the current hash immediately
    }

    /** Programmatic navigation */
    navigate(hash) {
        if (window.location.hash !== hash) {
            window.location.hash = hash;
        } else {
            this._navigate();  // Force re-render if already on same route
        }
    }

    /** @private */
    async _navigate() {
        if (this._navigating) return;
        this._navigating = true;

        const hash   = window.location.hash || CONFIG.ROUTES.DASHBOARD;
        const route  = this._routes.get(hash);
        const state  = store.getState();

        // Emit before-navigate event
        window.dispatchEvent(new CustomEvent("router:before-navigate", { detail: { hash, prev: this._currentHash } }));

        store.setState({ route: hash, isLoading: true });

        try {
            // --- Auth Guard ---
            const isPublic = CONFIG.PUBLIC_ROUTES.has(hash);

            if (!isPublic && !state.isAuthenticated) {
                // Try to silently restore session from cookie
                try {
                    const user = await api.getCurrentUser();
                    store.setUser(user);
                } catch {
                    // Session invalid — redirect to login
                    store.reset();
                    window.location.hash = CONFIG.ROUTES.LOGIN;
                    return;
                }
            }

            // --- Render ---
            if (!this._outlet) return;

            // Scroll to top on navigation
            this._outlet.scrollTop = 0;
            window.scrollTo(0, 0);

            if (!route) {
                document.title = `404 | ${DEFAULT_TITLE}`;
                render404(this._outlet);
                return;
            }

            // Protected route but not authenticated
            if (route.requiresAuth && !store.getState().isAuthenticated) {
                document.title = `Unauthorized | ${DEFAULT_TITLE}`;
                render401(this._outlet);
                return;
            }

            document.title = `${route.title} | ${DEFAULT_TITLE}`;
            this._outlet.innerHTML = "";
            await route.render(this._outlet);

            this._currentHash = hash;
        } finally {
            store.setState({ isLoading: false });
            this._navigating = false;

            // Emit after-navigate event
            window.dispatchEvent(new CustomEvent("router:after-navigate", { detail: { hash } }));
        }
    }

    destroy() {
        window.removeEventListener("hashchange", this._onHashChange);
    }
}

export const router = new Router();
