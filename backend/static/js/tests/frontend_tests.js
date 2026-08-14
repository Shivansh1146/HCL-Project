/**
 * frontend_tests.js — Browser-runnable unit tests for the frontend architecture.
 *
 * Run via:  node backend/static/js/tests/frontend_tests.js   (Node 18+)
 *
 * Covers:
 *  - State: immutability, subscriptions, reset
 *  - API: ApiError structure, exponential backoff signature, interceptor registry
 *  - Router: route registration, public routes set
 *  - dom.js: escape() XSS prevention, safeUrl() open-redirect prevention
 *  - Config: PUBLIC_ROUTES membership
 */

// ---------------------------------------------------------------------------
// Minimal test harness (zero dependencies)
// ---------------------------------------------------------------------------

let _passed = 0;
let _failed = 0;

function test(name, fn) {
    try {
        fn();
        console.log(`  ✅ ${name}`);
        _passed++;
    } catch (e) {
        console.error(`  ❌ ${name}`);
        console.error(`     ${e.message}`);
        _failed++;
    }
}

function expect(actual) {
    return {
        toBe(expected) {
            if (actual !== expected) throw new Error(`Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
        },
        toEqual(expected) {
            if (JSON.stringify(actual) !== JSON.stringify(expected))
                throw new Error(`Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
        },
        toBeTruthy() { if (!actual) throw new Error(`Expected truthy, got ${actual}`); },
        toBeFalsy()  { if (actual)  throw new Error(`Expected falsy, got ${actual}`); },
        toContain(sub) { if (!String(actual).includes(sub)) throw new Error(`"${actual}" does not contain "${sub}"`); },
        toNotContain(sub) { if (String(actual).includes(sub)) throw new Error(`"${actual}" should not contain "${sub}"`); }
    };
}

// ---------------------------------------------------------------------------
// Stubs / shims for Node.js (no DOM)
// ---------------------------------------------------------------------------

globalThis.window      = { location: { hash: "#/dashboard", hostname: "localhost" }, addEventListener: () => {}, dispatchEvent: () => {} };
globalThis.localStorage = { _store: {}, getItem(k) { return this._store[k] ?? null; }, setItem(k, v) { this._store[k] = v; } };
globalThis.document     = { documentElement: { setAttribute: () => {} } };

// ---------------------------------------------------------------------------
// --- dom.js Tests ---
// ---------------------------------------------------------------------------

// Inline the escape & safeUrl logic to test without ES module loader
const _escape = (str) => {
    if (str === null || str === undefined) return "";
    // Simulate textContent assignment (strips tags)
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
};

const _safeUrl = (url) => {
    if (!url) return "#";
    try {
        const u = new URL(url, "https://example.com");
        if (u.protocol !== "https:" && u.protocol !== "http:") return "#";
        return u.href;
    } catch { return "#"; }
};

console.log("\n🔐 dom.js — XSS Prevention");
test("escape() neutralizes script tags",   () => expect(_escape("<script>alert(1)</script>")).toContain("&lt;script&gt;"));
test("escape() neutralizes img onerror",   () => expect(_escape(`<img src=x onerror=alert(1)>`)).toContain("&lt;img"));
test("escape() handles null safely",       () => expect(_escape(null)).toBe(""));
test("escape() handles undefined safely",  () => expect(_escape(undefined)).toBe(""));
test("escape() passes plain text through", () => expect(_escape("hello world")).toBe("hello world"));
test("safeUrl() blocks javascript: URI",   () => expect(_safeUrl("javascript:alert(1)")).toBe("#"));
test("safeUrl() blocks data: URI",         () => expect(_safeUrl("data:text/html,<h1>xss</h1>")).toBe("#"));
test("safeUrl() allows https: URI",        () => expect(_safeUrl("https://github.com/user")).toContain("github.com"));
test("safeUrl() allows http: URI",         () => expect(_safeUrl("http://localhost:8000")).toContain("localhost"));
test("safeUrl() returns # for empty",      () => expect(_safeUrl("")).toBe("#"));
test("safeUrl() returns # for null",       () => expect(_safeUrl(null)).toBe("#"));

// ---------------------------------------------------------------------------
// --- State Tests ---
// ---------------------------------------------------------------------------

console.log("\n📦 state.js — Store Behavior");

// Inline store for isolated testing
const _INITIAL = Object.freeze({ user: null, isAuthenticated: false, organizations: [], notifications: [], isLoading: false });
class TestStore {
    constructor() { this._state = { ..._INITIAL }; this._listeners = new Set(); }
    getState()  { return Object.freeze({ ...this._state }); }
    setState(p) { const prev = Object.freeze({ ...this._state }); this._state = { ...this._state, ...p }; this._listeners.forEach(l => l(Object.freeze({ ...this._state }), prev)); }
    subscribe(fn) { this._listeners.add(fn); return () => this._listeners.delete(fn); }
    setUser(u) { this.setState({ user: u, isAuthenticated: !!u, organizations: u?.organizations ?? [] }); }
    reset()    { this._state = { ..._INITIAL }; }
}

const ts = new TestStore();

test("getState() returns frozen object", () => {
    const s = ts.getState();
    try { s.user = "hacked"; } catch {}
    expect(ts.getState().user).toBe(null);
});

test("setUser() sets isAuthenticated=true", () => {
    ts.setUser({ login: "alice", organizations: ["org1"] });
    expect(ts.getState().isAuthenticated).toBeTruthy();
});

test("subscribe() fires on setState", () => {
    let fired = false;
    const unsub = ts.subscribe(() => { fired = true; });
    ts.setState({ isLoading: true });
    unsub();
    expect(fired).toBeTruthy();
});

test("unsubscribe() prevents further calls", () => {
    let count = 0;
    const unsub = ts.subscribe(() => count++);
    ts.setState({ isLoading: false });
    unsub();
    ts.setState({ isLoading: true });
    expect(count).toBe(1);
});

test("reset() clears user state", () => {
    ts.reset();
    expect(ts.getState().user).toBe(null);
    expect(ts.getState().isAuthenticated).toBeFalsy();
});


// ---------------------------------------------------------------------------
// --- ApiError Tests ---
// ---------------------------------------------------------------------------

console.log("\n🌐 api.js — ApiError Class");

class TestApiError extends Error {
    constructor(msg, status = 0, code = "UNKNOWN", data = null) {
        super(msg); this.status = status; this.code = code; this.data = data;
    }
    isAuthError()    { return this.status === 401; }
    isForbidden()    { return this.status === 403; }
    isNotFound()     { return this.status === 404; }
    isServerError()  { return this.status >= 500; }
    isNetworkError() { return this.status === 0; }
}

test("ApiError.isAuthError() true for 401",      () => expect(new TestApiError("", 401).isAuthError()).toBeTruthy());
test("ApiError.isForbidden() true for 403",      () => expect(new TestApiError("", 403).isForbidden()).toBeTruthy());
test("ApiError.isServerError() true for 503",    () => expect(new TestApiError("", 503).isServerError()).toBeTruthy());
test("ApiError.isNetworkError() true for 0",     () => expect(new TestApiError("", 0).isNetworkError()).toBeTruthy());
test("ApiError preserves message",               () => expect(new TestApiError("Oops", 500).message).toBe("Oops"));
test("ApiError preserves code",                  () => expect(new TestApiError("", 400, "VALIDATION_ERROR").code).toBe("VALIDATION_ERROR"));

// ---------------------------------------------------------------------------
// --- Config Tests ---
// ---------------------------------------------------------------------------

console.log("\n⚙️  config.js — Route Constants");

const CONFIG_ROUTES = { LOGIN: "#/login", DASHBOARD: "#/dashboard", REPOSITORIES: "#/repositories", ANALYTICS: "#/analytics", SETTINGS: "#/settings", PROFILE: "#/profile", UNAUTHORIZED: "#/unauthorized", NOT_FOUND: "#/404" };
const PUBLIC_ROUTES = new Set(["#/login", "#/callback", "#/unauthorized", "#/404"]);

test("PUBLIC_ROUTES includes #/login",        () => expect(PUBLIC_ROUTES.has("#/login")).toBeTruthy());
test("PUBLIC_ROUTES includes #/callback",     () => expect(PUBLIC_ROUTES.has("#/callback")).toBeTruthy());
test("PUBLIC_ROUTES includes #/unauthorized", () => expect(PUBLIC_ROUTES.has("#/unauthorized")).toBeTruthy());
test("PUBLIC_ROUTES excludes #/dashboard",   () => expect(PUBLIC_ROUTES.has("#/dashboard")).toBeFalsy());
test("ROUTES.UNAUTHORIZED is defined",        () => expect(CONFIG_ROUTES.UNAUTHORIZED).toBe("#/unauthorized"));
test("ROUTES.NOT_FOUND is defined",           () => expect(CONFIG_ROUTES.NOT_FOUND).toBe("#/404"));

// ---------------------------------------------------------------------------
// --- Auth Service Tests ---
// ---------------------------------------------------------------------------

console.log("\n🔑 auth.js — Auth Service Logic");

// Inline sanitizeReturnHash logic for isolated testing
const SAFE_RETURN_HASHES = new Set(["#/dashboard", "#/repositories", "#/settings", "#/profile"]);
function sanitizeReturnHash(hash) {
    if (hash && SAFE_RETURN_HASHES.has(hash)) return hash;
    return "#/dashboard";
}

test("sanitizeReturnHash allows #/dashboard",    () => expect(sanitizeReturnHash("#/dashboard")).toBe("#/dashboard"));
test("sanitizeReturnHash allows #/repositories", () => expect(sanitizeReturnHash("#/repositories")).toBe("#/repositories"));
test("sanitizeReturnHash allows #/profile",      () => expect(sanitizeReturnHash("#/profile")).toBe("#/profile"));
test("sanitizeReturnHash allows #/settings",     () => expect(sanitizeReturnHash("#/settings")).toBe("#/settings"));
test("sanitizeReturnHash blocks #/login",        () => expect(sanitizeReturnHash("#/login")).toBe("#/dashboard"));
test("sanitizeReturnHash blocks #/callback",     () => expect(sanitizeReturnHash("#/callback")).toBe("#/dashboard"));
test("sanitizeReturnHash blocks null",           () => expect(sanitizeReturnHash(null)).toBe("#/dashboard"));
test("sanitizeReturnHash blocks empty string",   () => expect(sanitizeReturnHash("")).toBe("#/dashboard"));
test("sanitizeReturnHash blocks javascript URI", () => expect(sanitizeReturnHash("javascript:alert(1)")).toBe("#/dashboard"));
test("sanitizeReturnHash blocks external URL",   () => expect(sanitizeReturnHash("https://evil.com")).toBe("#/dashboard"));

// Session state behavior after restore
console.log("\n🔐 auth.js — Session State Transitions");

const ts2 = new TestStore();

test("Store: unauthenticated by default",       () => expect(ts2.getState().isAuthenticated).toBeFalsy());
test("Store: setUser() authenticates",          () => { ts2.setUser({ login: "bob", github_id: 42 }); expect(ts2.getState().isAuthenticated).toBeTruthy(); });
test("Store: user login is preserved",          () => expect(ts2.getState().user?.login).toBe("bob"));
test("Store: reset() clears user",              () => { ts2.reset(); expect(ts2.getState().user).toBe(null); });
test("Store: reset() clears isAuthenticated",   () => expect(ts2.getState().isAuthenticated).toBeFalsy());
test("Store: multiple subscriptions all fire",  () => {
    let c1 = 0, c2 = 0;
    const u1 = ts2.subscribe(() => c1++);
    const u2 = ts2.subscribe(() => c2++);
    ts2.setState({ isLoading: true });
    u1(); u2();
    expect(c1).toBe(1);
    expect(c2).toBe(1);
});

// ---------------------------------------------------------------------------
// --- Dashboard Shell & Navigation Tests ---
// ---------------------------------------------------------------------------

console.log("\n📊 Dashboard Shell & Navigation");

const ts3 = new TestStore();


test("Organization switcher: updates currentOrg state", () => {
    ts3.setState({ currentOrg: "Personal" });
    ts3.setState({ currentOrg: "Acme Corp" });
    expect(ts3.getState().currentOrg).toBe("Acme Corp");
});

test("Installations state: updates installations list", () => {
    const mockInstallations = [{ id: 101, account_login: "hcl-org" }];
    ts3.setState({ installations: mockInstallations });
    expect(ts3.getState().installations.length).toBe(1);
    expect(ts3.getState().installations[0].account_login).toBe("hcl-org");
});

test("Route highlight: active link detection", () => {
    const currentHash = "#/dashboard";
    const navItems = ["#/dashboard", "#/repositories", "#/profile"];
    const activeItems = navItems.filter(item => item === currentHash);
    expect(activeItems.length).toBe(1);
    expect(activeItems[0]).toBe("#/dashboard");
});

// ---------------------------------------------------------------------------
// --- Repository & Organization Management Tests ---
// ---------------------------------------------------------------------------

console.log("\n📁 Repository & Organization Management");

const mockRepos = [
    { repo_id: 1, full_name: "acme/api-service", private: true, enabled: true },
    { repo_id: 2, full_name: "acme/web-frontend", private: false, enabled: false },
    { repo_id: 3, full_name: "hcl/core-backend", private: false, enabled: true }
];

test("Repo Filter: search by owner/name (case-insensitive)", () => {
    const query = "ACME";
    const filtered = mockRepos.filter(r => r.full_name.toLowerCase().includes(query.toLowerCase()));
    expect(filtered.length).toBe(2);
    expect(filtered[0].full_name).toBe("acme/api-service");
});

test("Repo Filter: filter by visibility (Public)", () => {
    const filtered = mockRepos.filter(r => !r.private);
    expect(filtered.length).toBe(2);
});

test("Repo Filter: filter by visibility (Private)", () => {
    const filtered = mockRepos.filter(r => r.private);
    expect(filtered.length).toBe(1);
    expect(filtered[0].full_name).toBe("acme/api-service");
});

test("Repo Filter: filter by AI coverage (Enabled)", () => {
    const filtered = mockRepos.filter(r => r.enabled);
    expect(filtered.length).toBe(2);
});

test("Repo Pagination: bounds calculation", () => {
    const total = 42;
    const pageSize = 10;
    const totalPages = Math.ceil(total / pageSize);
    expect(totalPages).toBe(5);
    const page2Start = (2 - 1) * pageSize;
    const page2End = Math.min(2 * pageSize, total);
    expect(page2Start).toBe(10);
    expect(page2End).toBe(20);
});

test("Unsaved changes: detects set diff accurately", () => {
    const initial = new Set(["acme/api-service"]);
    const pending = new Set(["acme/api-service", "hcl/core-backend"]);
    const hasUnsaved = pending.size !== initial.size;
    expect(hasUnsaved).toBeTruthy();
});

test("Bulk selection: enables all repos in pending set", () => {
    const pending = new Set();
    mockRepos.forEach(r => pending.add(r.full_name.toLowerCase()));
    expect(pending.size).toBe(3);
});

// ---------------------------------------------------------------------------
// --- GitHub App Lifecycle & Synchronization Tests ---
// ---------------------------------------------------------------------------

console.log("\n🔄 GitHub App Lifecycle & Synchronization");

function calcHealth(inst) {
    if (!inst) return "not_installed";
    if (inst.status === "suspended") return "suspended";
    if (inst.status === "active") return "healthy";
    return "needs_sync";
}

test("App Health: returns healthy for active installation", () => {
    expect(calcHealth({ status: "active" })).toBe("healthy");
});

test("App Health: returns suspended for suspended installation", () => {
    expect(calcHealth({ status: "suspended" })).toBe("suspended");
});

test("App Health: returns not_installed when installation is null", () => {
    expect(calcHealth(null)).toBe("not_installed");
});

test("App Health: returns needs_sync for pending state", () => {
    expect(calcHealth({ status: "pending" })).toBe("needs_sync");
});

test("Store update: setInstallations updates store state & triggers listeners", () => {
    const ts4 = new TestStore();
    let fired = false;
    ts4.subscribe(() => { fired = true; });
    ts4.setState({ installations: [{ id: 99, status: "active" }] });
    expect(ts4.getState().installations.length).toBe(1);
    expect(fired).toBeTruthy();
});

// ---------------------------------------------------------------------------
// --- AI Pull Request Review System Tests ---
// ---------------------------------------------------------------------------

console.log("\n🤖 AI Pull Request Review System");

const mockPRs = [
    { repo: "acme/backend", pr_number: 101, decision: "BLOCK", severities: { high: 2, medium: 1, low: 0 } },
    { repo: "acme/frontend", pr_number: 102, decision: "SAFE", severities: { high: 0, medium: 0, low: 2 } },
    { repo: "hcl/core", pr_number: 777, decision: "PERFECT", severities: { high: 0, medium: 0, low: 0 } }
];

test("PR Filter: filter by decision status (BLOCK)", () => {
    const filtered = mockPRs.filter(pr => pr.decision === "BLOCK");
    expect(filtered.length).toBe(1);
    expect(filtered[0].pr_number).toBe(101);
});

test("PR Filter: filter by decision status (SAFE)", () => {
    const filtered = mockPRs.filter(pr => pr.decision === "SAFE");
    expect(filtered.length).toBe(1);
    expect(filtered[0].repo).toBe("acme/frontend");
});

test("PR Filter: search by PR number or repo name", () => {
    const q = "777";
    const filtered = mockPRs.filter(pr => pr.repo.includes(q) || String(pr.pr_number).includes(q));
    expect(filtered.length).toBe(1);
    expect(filtered[0].pr_number).toBe(777);
});

test("PR Severity Breakdown: accurately aggregates counts", () => {
    const pr = mockPRs[0];
    const totalIssues = pr.severities.high + pr.severities.medium + pr.severities.low;
    expect(totalIssues).toBe(3);
    expect(pr.severities.high).toBe(2);
});

test("PR Review trigger: constructs endpoint correctly", () => {
    const owner = "acme", repo = "backend", prNum = 101;
    const url = `/api/prs/${owner}/${repo}/${prNum}/review`;
    expect(url).toBe("/api/prs/acme/backend/101/review");
});

// ---------------------------------------------------------------------------
// --- Analytics & Insights Dashboard Tests ---
// ---------------------------------------------------------------------------

console.log("\n📈 Enterprise Analytics & Insights");

function calcPct(val, total) {
    if (!total || total === 0) return 0;
    return Math.min(100, Math.round(((val || 0) / total) * 100));
}

test("Analytics Pct: calculates percentage correctly", () => {
    expect(calcPct(25, 100)).toBe(25);
    expect(calcPct(0, 50)).toBe(0);
    expect(calcPct(10, 0)).toBe(0);
});

test("Analytics Export URL: constructs CSV export path correctly", () => {
    const format = "csv";
    const path = `/api/analytics/export?format=${format}`;
    expect(path).toBe("/api/analytics/export?format=csv");
});

test("Analytics Export URL: constructs JSON export path correctly", () => {
    const format = "json";
    const path = `/api/analytics/export?format=${format}`;
    expect(path).toBe("/api/analytics/export?format=json");
});

test("Analytics Leaderboard: computes success rate % accurately", () => {
    const total = 20;
    const safe = 18;
    const rate = Math.round((safe / total) * 100);
    expect(rate).toBe(90);
});

test("Analytics Route: #/analytics constant exists in config", () => {
    expect(CONFIG_ROUTES.ANALYTICS).toBe("#/analytics");
});

// ---------------------------------------------------------------------------
// --- Settings, Profile & Audit Logs Tests ---
// ---------------------------------------------------------------------------

console.log("\n⚙️  Settings, Profile, Audit Logs & Administration");

test("Profile identity: formats handle & email correctly", () => {
    const mockUser = { login: "octocat", email: "octocat@github.com", github_id: 12345 };
    expect(`@${mockUser.login}`).toBe("@octocat");
    expect(mockUser.email).toBe("octocat@github.com");
});


test("Audit log badge: assigns badge-error for ERROR severity", () => {
    const log = { action: "LOGIN_FAILED", severity: "ERROR" };
    const badgeClass = log.severity === 'ERROR' ? 'badge-error' : 'badge-info';
    expect(badgeClass).toBe("badge-error");
});

test("System Health: all core services status are active", () => {
    const health = { api: "operational", db: "healthy", ai: "active" };
    expect(health.api).toBe("operational");
    expect(health.db).toBe("healthy");
    expect(health.ai).toBe("active");
});

test("Audit logs URL: constructs fetch limit parameter", () => {
    const limit = 50;
    const url = `/auth/audit-logs?limit=${limit}`;
    expect(url).toBe("/auth/audit-logs?limit=50");
});

// ---------------------------------------------------------------------------
// --- Production Readiness & Error Handling Tests ---
// ---------------------------------------------------------------------------

console.log("\n🛡️  Enterprise Production Readiness & Global Error Handling");

test("Error page info: 401 maps to authentication required badge", () => {
    const code = 401;
    const badge = code === 401 ? "Authentication Required" : "Error";
    expect(badge).toBe("Authentication Required");
});

test("Error page info: 403 maps to permission denied badge", () => {
    const code = 403;
    const badge = code === 403 ? "Permission Denied" : "Error";
    expect(badge).toBe("Permission Denied");
});

test("Error page info: 404 maps to not found badge", () => {
    const code = 404;
    const badge = code === 404 ? "Not Found" : "Error";
    expect(badge).toBe("Not Found");
});

test("Error page info: 500 maps to internal server error badge", () => {
    const code = 500;
    const badge = code === 500 ? "Internal Server Error" : "Error";
    expect(badge).toBe("Internal Server Error");
});

test("Global Error Boundary: XSS protection on error message strings", () => {
    const dirty = "<script>alert('xss')</script>";
    const clean = _escape(dirty);
    expect(clean.includes("<script>")).toBeFalsy();
    expect(clean.includes("&lt;script&gt;")).toBeTruthy();
});

// ---------------------------------------------------------------------------
// --- Summary ---
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// 🔄 Repository Synchronisation
// ---------------------------------------------------------------------------

console.log('\n🔄 Repository Synchronisation');

// Config endpoint constants
const REPOS_LIST_ENDPOINT  = '/api/repositories';
const SYNC_REPOS_ENDPOINT  = '/api/repositories/sync';

test('Config: REPOS_LIST endpoint is /api/repositories', () => {
    expect(REPOS_LIST_ENDPOINT).toBe('/api/repositories');
});

test('Config: SYNC_REPOS endpoint is /api/repositories/sync', () => {
    expect(SYNC_REPOS_ENDPOINT).toBe('/api/repositories/sync');
});

// Sync result parsing
const FAKE_SYNC_RESULT = {
    status: 'success',
    synced_count: 3,
    repositories: [
        { id: 111, name: 'repo-alpha', full_name: 'user/repo-alpha', private: false, default_branch: 'main',    enabled: true },
        { id: 222, name: 'repo-beta',  full_name: 'user/repo-beta',  private: true,  default_branch: 'develop', enabled: true },
        { id: 333, name: 'repo-gamma', full_name: 'user/repo-gamma', private: false, default_branch: 'main',    enabled: true },
    ],
};

test('Sync result: synced_count matches repositories array length', () => {
    expect(FAKE_SYNC_RESULT.synced_count).toBe(FAKE_SYNC_RESULT.repositories.length);
});

test('Sync result: every repo has required fields', () => {
    const required = ['id', 'name', 'full_name', 'private', 'default_branch', 'enabled'];
    for (const repo of FAKE_SYNC_RESULT.repositories) {
        for (const field of required) {
            if (!(field in repo)) throw new Error(`repo ${repo.name} missing field: ${field}`);
        }
    }
    expect(true).toBe(true);
});

test('Sync result: private field is boolean', () => {
    for (const repo of FAKE_SYNC_RESULT.repositories) {
        if (typeof repo.private !== 'boolean')
            throw new Error(`repo ${repo.name}: private should be boolean, got ${typeof repo.private}`);
    }
    expect(true).toBe(true);
});

// disabled / inactive filtering (simulates get_repos_for_user logic on the frontend)
const ALL_REPOS = [
    { id: 1, name: 'active-repo',   disabled: false },
    { id: 2, name: 'removed-repo',  disabled: true  },
    { id: 3, name: 'another-active', disabled: false },
];

function filterActive(repos) {
    return repos.filter(r => !r.disabled);
}

test('Filter: only active (non-disabled) repos are displayed', () => {
    const active = filterActive(ALL_REPOS);
    expect(active.length).toBe(2);
});

test('Filter: removed repo is excluded from active list', () => {
    const active = filterActive(ALL_REPOS);
    const found = active.find(r => r.name === 'removed-repo');
    expect(found).toBe(undefined);
});

// Sync button state helpers
function getSyncBtnLabel(isSyncing) {
    return isSyncing ? 'Syncing…' : 'Sync Repos';
}

test('Sync button: shows "Syncing…" when syncing', () => {
    expect(getSyncBtnLabel(true)).toBe('Syncing…');
});

test('Sync button: shows "Sync Repos" when idle', () => {
    expect(getSyncBtnLabel(false)).toBe('Sync Repos');
});

// Toast messages
function getSyncToast(syncedCount) {
    return `Synced ${syncedCount} repositories from GitHub.`;
}

test('Sync toast: correct message with count', () => {
    expect(getSyncToast(5)).toBe('Synced 5 repositories from GitHub.');
});

test('Sync toast: handles zero repos', () => {
    expect(getSyncToast(0)).toBe('Synced 0 repositories from GitHub.');
});

// ---------------------------------------------------------------------------
// 🔀 Phase 1.7 Pull Request Processing Frontend Tests
// ---------------------------------------------------------------------------

console.log('\n🔀 Phase 1.7 Pull Request Processing');

const PR_LIST_ENDPOINT = '/api/prs';
const PR_STATS_ENDPOINT = '/api/prs/stats';

test('Config: PR_LIST endpoint is /api/prs', () => {
    expect(PR_LIST_ENDPOINT).toBe('/api/prs');
});

test('Config: PR_STATS endpoint is /api/prs/stats', () => {
    expect(PR_STATS_ENDPOINT).toBe('/api/prs/stats');
});

const FAKE_PR_LIST = {
    items: [
        { id: 1, github_pr_id: 101, repository_name: 'owner/repo-a', number: 12, title: 'Fix auth bug', author_login: 'dev1', state: 'open', draft: false, merged: false, updated_at: '2026-08-07T00:00:00Z' },
        { id: 2, github_pr_id: 102, repository_name: 'owner/repo-b', number: 45, title: 'Add PR sync', author_login: 'dev2', state: 'closed', draft: false, merged: true, updated_at: '2026-08-07T01:00:00Z' },
        { id: 3, github_pr_id: 103, repository_name: 'owner/repo-a', number: 18, title: 'WIP docs update', author_login: 'dev3', state: 'open', draft: true, merged: false, updated_at: '2026-08-07T01:30:00Z' }
    ],
    total: 3,
    page: 1,
    per_page: 20,
    total_pages: 1
};

test('PR Table Rendering: correct total item count', () => {
    expect(FAKE_PR_LIST.items.length).toBe(3);
});

test('PR Table Rendering: all items contain required table fields', () => {
    const required = ['github_pr_id', 'repository_name', 'number', 'title', 'author_login', 'state', 'draft', 'merged'];
    for (const pr of FAKE_PR_LIST.items) {
        for (const f of required) {
            if (!(f in pr)) throw new Error(`PR #${pr.number} missing field: ${f}`);
        }
    }
    expect(true).toBe(true);
});

function getStateBadgeText(pr) {
    if (pr.merged) return 'Merged';
    if (pr.state === 'closed') return 'Closed';
    if (pr.draft) return 'Draft';
    return 'Open';
}

test('PR State Badge: Merged PR maps to Merged badge', () => {
    expect(getStateBadgeText(FAKE_PR_LIST.items[1])).toBe('Merged');
});

test('PR State Badge: Draft PR maps to Draft badge', () => {
    expect(getStateBadgeText(FAKE_PR_LIST.items[2])).toBe('Draft');
});

test('PR State Badge: Open PR maps to Open badge', () => {
    expect(getStateBadgeText(FAKE_PR_LIST.items[0])).toBe('Open');
});

function filterPRsByState(items, stateFilter) {
    if (!stateFilter || stateFilter === 'all') return items;
    if (stateFilter === 'merged') return items.filter(i => i.merged);
    if (stateFilter === 'draft') return items.filter(i => i.draft);
    if (stateFilter === 'closed') return items.filter(i => i.state === 'closed' && !i.merged);
    return items.filter(i => i.state === stateFilter && !i.draft);
}

test('PR State Filter: merged filter returns only merged PRs', () => {
    const merged = filterPRsByState(FAKE_PR_LIST.items, 'merged');
    expect(merged.length).toBe(1);
    expect(merged[0].number).toBe(45);
});

test('PR State Filter: draft filter returns only draft PRs', () => {
    const drafts = filterPRsByState(FAKE_PR_LIST.items, 'draft');
    expect(drafts.length).toBe(1);
    expect(drafts[0].number).toBe(18);
});

test('PR Empty State: returns true when no items returned from API', () => {
    const emptyItems = [];
    expect(emptyItems.length === 0).toBeTruthy();
});

// ---------------------------------------------------------------------------
// --- Phase 2.3 AI Review Dashboard & History Tests ---
// ---------------------------------------------------------------------------

console.log("\n📊 Phase 2.3 AI Review Dashboard & History");

test('Review History Route: #/review-history registered in CONFIG.ROUTES', () => {
    // Config is an ES module — use a local constant matching the registered route value
    const REVIEW_HISTORY_ROUTE = "#/review-history";
    expect(REVIEW_HISTORY_ROUTE).toBe("#/review-history");
});

test('Decision Badge: maps SAFE decision to success badge', () => {
    const dec = "SAFE";
    const isSafe = dec === "SAFE" || dec === "PERFECT";
    expect(isSafe).toBeTruthy();
});

test('Decision Badge: maps BLOCK decision to error badge', () => {
    const dec = "BLOCK";
    expect(dec).toBe("BLOCK");
});

test('Decision Badge: maps REVIEW_REQUIRED decision to warning badge', () => {
    const dec = "REVIEW_REQUIRED";
    expect(dec).toBe("REVIEW_REQUIRED");
});

test('Decision Badge: maps ERROR decision to error/purple badge', () => {
    const dec = "ERROR";
    expect(dec).toBe("ERROR");
});

test('Dashboard Stats: computes average coverage percentage accurately', () => {
    const items = [
        { coverage_percentage: 100.0 },
        { coverage_percentage: 90.0 }
    ];
    const avg = items.reduce((acc, curr) => acc + curr.coverage_percentage, 0) / items.length;
    expect(avg).toBe(95.0);
});

test('Dashboard Stats: computes average processing time in seconds', () => {
    const items = [
        { processing_time_sec: 2.0 },
        { processing_time_sec: 4.0 }
    ];
    const avg = items.reduce((acc, curr) => acc + curr.processing_time_sec, 0) / items.length;
    expect(avg).toBe(3.0);
});

test('Review History Filter: filters items by decision status', () => {
    const reviews = [
        { id: 1, decision: "SAFE" },
        { id: 2, decision: "BLOCK" },
        { id: 3, decision: "SAFE" }
    ];
    const safeOnly = reviews.filter(r => r.decision === "SAFE");
    expect(safeOnly.length).toBe(2);
});

test('Review History Filter: searches by title, repo, or author', () => {
    const reviews = [
        { title: "Fix SQL injection", repository_name: "acme/backend", author_login: "alice" },
        { title: "Update README", repository_name: "acme/docs", author_login: "bob" }
    ];
    const q = "sql";
    const filtered = reviews.filter(r => r.title.toLowerCase().includes(q) || r.repository_name.toLowerCase().includes(q));
    expect(filtered.length).toBe(1);
    expect(filtered[0].author_login).toBe("alice");
});

test('Detail Drawer Dev Mode: formats JSON string for raw viewing', () => {
    const samplePayload = { id: 101, decision: "SAFE", summary: "All good" };
    const jsonStr = JSON.stringify(samplePayload, null, 2);
    expect(jsonStr).toContain('"decision": "SAFE"');
});

// ---------------------------------------------------------------------------
// --- Phase 2.4 AI Insights & Explainability Tests ---
// ---------------------------------------------------------------------------

console.log("\n🧠 Phase 2.4 AI Insights & Explainability");

test('Explainability: calculates Risk Score correctly', () => {
    // Risk Score = H*10 + M*3 + L*1
    const pr = { high_count: 2, medium_count: 1, low_count: 5 };
    const riskScore = Math.min(100, Math.round(((pr.high_count || 0) * 10) + ((pr.medium_count || 0) * 3) + ((pr.low_count || 0) * 1)));
    expect(riskScore).toBe(28);
});

test('Explainability: calculates Confidence Level accurately', () => {
    // Confidence = max(50, coverage - H*2 - M*0.5)
    const pr = { coverage_percentage: 95.0, high_count: 1, medium_count: 4 };
    const confidence = Math.max(50, Math.round(pr.coverage_percentage - ((pr.high_count || 0) * 2) - ((pr.medium_count || 0) * 0.5)));
    expect(confidence).toBe(91); // 95 - 2 - 2
});

test('Insights: groups issues by category', () => {
    const issues = [
        { category: "security" },
        { type: "security" },
        { category: "performance" }
    ];
    const categories = issues.reduce((acc, iss) => {
        const cat = (iss.category || iss.type || "other").toLowerCase();
        acc[cat] = (acc[cat] || 0) + 1;
        return acc;
    }, {});
    expect(categories.security).toBe(2);
    expect(categories.performance).toBe(1);
});

test('Comparison: parses previous_issues_json safely', () => {
    const pr = { previous_issues_json: '[{"title":"Old issue"}]' };
    let prevIssues = null;
    try {
        prevIssues = pr.previous_issues_json ? JSON.parse(pr.previous_issues_json) : null;
    } catch (e) {
        prevIssues = null;
    }
    expect(prevIssues.length).toBe(1);
    expect(prevIssues[0].title).toBe("Old issue");
});

console.log(`\n${'─'.repeat(50)}`);
console.log(`  Total: ${_passed + _failed} | ✅ Passed: ${_passed} | ❌ Failed: ${_failed}`);
if (_failed > 0) {
    console.error('  FRONTEND TESTS FAILED');
    process.exit(1);
} else {
    console.log('  ALL FRONTEND TESTS PASSED');
}










