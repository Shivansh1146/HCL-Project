/**
 * app.js — Application Shell & Entry Point.
 *
 * Responsibilities:
 *  1. Build the app shell DOM (sidebar + header + page outlet + mobile backdrop)
 *  2. Restore session via authService (silent GET /auth/me)
 *  3. Register all routes with the router
 *  4. Start the router (handles auth guard, 404, 401)
 *  5. Mount top header and sidebar with reactive subscriptions
 */

import { store }           from "./utils/state.js";
import { authService }     from "./services/auth.js";
import { router }          from "./services/router.js";
import { renderSidebar }   from "./components/sidebar.js";
import { renderHeader }    from "./components/header.js";
import { Toast }           from "./components/toast.js";
import { CONFIG }          from "./config/config.js";

async function bootstrapApp() {
    const appRoot = document.getElementById("app-root");
    if (!appRoot) {
        console.error("[App] Fatal: #app-root not found.");
        return;
    }

    // 1. Build the application shell layout
    appRoot.innerHTML = `
        <div class="app-shell">
            <div id="sidebar-backdrop" class="sidebar-backdrop"></div>
            <aside id="sidebar" aria-label="Primary navigation"></aside>
            <div class="main-wrapper">
                <header class="top-header" id="top-header" role="banner"></header>
                <main id="page-outlet" class="page-content" role="main" aria-live="polite">
                    <div style="display:flex;align-items:center;justify-content:center;height:60vh;">
                        <div class="spinner" aria-label="Loading application"></div>
                    </div>
                </main>
            </div>
        </div>
    `;

    // Backdrop click listener for mobile navigation drawer
    const backdrop = document.getElementById("sidebar-backdrop");
    const sidebar  = document.getElementById("sidebar");
    backdrop?.addEventListener("click", () => {
        sidebar?.classList.remove("mobile-open");
        backdrop?.classList.remove("active");
    });

    // 2. Default theme is set in CSS, no JS theme application required
    // 3. Attempt session restoration from HttpOnly cookie
    try {
        await authService.restoreSession();
    } catch (err) {
        console.warn("[App] Session restore failed (network issue):", err?.message);
    }

    // 4. Mount Top Header and Sidebar
    const headerEl  = document.getElementById("top-header");
    const sidebarEl = document.getElementById("sidebar");

    function mountLayoutComponents() {
        renderHeader(headerEl);
        renderSidebar(sidebarEl);
    }

    mountLayoutComponents();

    // Subscribe layout components to store updates (auth, orgs)
    store.subscribe(() => {
        mountLayoutComponents();
    });

    // 5. Register all SPA routes
    const outlet = document.getElementById("page-outlet");
    router.setOutlet(outlet);

    router
        .register(CONFIG.ROUTES.LOGIN,         async (el) => { const { renderLoginPage }        = await import("./pages/login.js");        await renderLoginPage(el);        }, { title: "Sign In",       requiresAuth: false })
        .register(CONFIG.ROUTES.DASHBOARD,     async (el) => { const { renderDashboardPage }     = await import("./pages/dashboard.js");    await renderDashboardPage(el);     }, { title: "Dashboard",      requiresAuth: true  })
        .register(CONFIG.ROUTES.REPOSITORIES,  async (el) => { const { renderReposPage }         = await import("./pages/repositories.js"); await renderReposPage(el);         }, { title: "Repositories",   requiresAuth: true  })
        .register(CONFIG.ROUTES.PULL_REQUESTS, async (el) => { const { renderPullRequestsPage } = await import("./pages/pull_requests.js");await renderPullRequestsPage(el); }, { title: "Pull Requests",  requiresAuth: true  })
        .register(CONFIG.ROUTES.REVIEW_HISTORY, async (el) => { const { renderReviewHistoryPage } = await import("./pages/review_history.js");await renderReviewHistoryPage(el); }, { title: "Review History", requiresAuth: true  })
        .register(CONFIG.ROUTES.ANALYTICS,     async (el) => { const { renderAnalyticsPage }    = await import("./pages/analytics.js");    await renderAnalyticsPage(el);     }, { title: "Analytics",      requiresAuth: true  })
        .register("#/organizations",           async (el) => { const { renderOrganizationsPage } = await import("./pages/organizations.js");await renderOrganizationsPage(el); }, { title: "Organizations",  requiresAuth: true  })
        .register(CONFIG.ROUTES.PROFILE,       async (el) => { const { renderProfilePage }       = await import("./pages/profile.js");      await renderProfilePage(el);       }, { title: "Profile",        requiresAuth: true  })
        .register(CONFIG.ROUTES.SETTINGS,      async (el) => { const { renderSettingsPage }      = await import("./pages/settings.js");     await renderSettingsPage(el);      }, { title: "Settings",       requiresAuth: true  })
        .register(CONFIG.ROUTES.UNAUTHORIZED,  async (el) => { const { renderErrorPage }         = await import("./pages/error.js");        renderErrorPage(el, 401);          }, { title: "Unauthorized",   requiresAuth: false })
        .register(CONFIG.ROUTES.NOT_FOUND,     async (el) => { const { renderErrorPage }         = await import("./pages/error.js");        renderErrorPage(el, 404);          }, { title: "Page Not Found", requiresAuth: false })
        .register("#/callback",                async (el) => { const { renderCallbackPage }      = await import("./pages/callback.js");     await renderCallbackPage(el);      }, { title: "Signing in…",    requiresAuth: false });

    // 6. Navigation breadcrumbs update listener
    window.addEventListener("router:after-navigate", (e) => {
        const breadcrumb = document.getElementById("page-breadcrumb");
        if (!breadcrumb) return;
        const labels = {
            [CONFIG.ROUTES.DASHBOARD]: "Dashboard",
            [CONFIG.ROUTES.REPOSITORIES]: "Repositories",
            [CONFIG.ROUTES.PULL_REQUESTS]: "Pull Requests",
            [CONFIG.ROUTES.REVIEW_HISTORY]: "Review History",
            [CONFIG.ROUTES.ANALYTICS]: "Analytics",
            "#/organizations": "Organizations",
            [CONFIG.ROUTES.PROFILE]: "Profile",
            [CONFIG.ROUTES.SETTINGS]: "Settings"
        };

        breadcrumb.textContent = labels[e.detail.hash] || "Command Center";

        // Hide sidebar/header chrome on public auth pages (login, callback)
        const isAuthPage = CONFIG.PUBLIC_ROUTES.has(e.detail.hash);
        document.body.classList.toggle("auth-page", isAuthPage);

        // Close mobile drawer on route change
        sidebar?.classList.remove("mobile-open");
        backdrop?.classList.remove("active");
    });

    // 7. Start router
    await router.start();

    // 8. Reveal body
    document.body.classList.add("loaded");
}

bootstrapApp().catch(err => {
    console.error("[App] Fatal bootstrap error:", err);
    Toast.error("Application failed to start. Please refresh the page.");
    document.body.classList.add("loaded");
});
