/**
 * state.js — Immutable pub/sub global state container.
 *
 * Improvements over v1:
 *  - getState() returns a frozen deep copy (prevents external mutation)
 *  - subscribe() returns unsubscribe fn — callers MUST call it to prevent memory leaks
 *  - reset() clears auth/user state on logout (prevents session bleed)
 *  - Organization and installation state included
 */

/** @type {Readonly<AppState>} */
const INITIAL_STATE = Object.freeze({
    user:            null,
    isAuthenticated: false,
    currentOrg:      null,
    organizations:   [],
    installations:   [],
    selectedRepos:   [],
    notifications:   [],
    route:           window.location.hash || "#/dashboard",
    isLoading:       false,
});

class Store {
    constructor() {
        /** @private */
        this._state = { ...INITIAL_STATE };
        /** @private @type {Set<Function>} */
        this._listeners = new Set();
    }

    /**
     * Returns a frozen snapshot of the current state.
     * Prevents callers from directly mutating the state object.
     * @returns {Readonly<AppState>}
     */
    getState() {
        return Object.freeze({ ...this._state });
    }

    /**
     * Merges partialState into current state and notifies all subscribers.
     * @param {Partial<AppState>} partialState
     */
    setState(partialState) {
        const prevState = Object.freeze({ ...this._state });
        this._state = { ...this._state, ...partialState };
        this._notify(Object.freeze({ ...this._state }), prevState);
    }

    /**
     * Subscribe to state changes.
     * @param {(newState: AppState, prevState: AppState) => void} listener
     * @returns {() => void} Unsubscribe function — MUST be called to prevent memory leaks
     */
    subscribe(listener) {
        this._listeners.add(listener);
        return () => this._listeners.delete(listener);
    }

    /** @private */
    _notify(newState, prevState) {
        this._listeners.forEach(listener => {
            try { listener(newState, prevState); }
            catch (e) { console.error("[Store] Listener error:", e); }
        });
    }

    // ---------------------------------------------------------------------------
    // Semantic State Updaters
    // ---------------------------------------------------------------------------

    setUser(user) {
        this.setState({
            user,
            isAuthenticated: !!user,
            organizations:   user?.organizations ?? [],
        });
    }

    setCurrentOrg(org) {
        this.setState({ currentOrg: org });
    }

    setInstallations(installations) {
        this.setState({ installations });
    }

    setSelectedRepos(repos) {
        this.setState({ selectedRepos: repos });
    }

    setLoading(isLoading) {
        this.setState({ isLoading });
    }

    addNotification(notification) {
        const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
        this.setState({
            notifications: [...this._state.notifications, { id, ...notification }]
        });
        return id;
    }

    removeNotification(id) {
        this.setState({
            notifications: this._state.notifications.filter(n => n.id !== id)
        });
    }

    /**
     * Resets all auth-related state on logout.
     * Preserves route preferences.
     */
    reset() {
        this._state = {
            ...INITIAL_STATE,
            notifications: [],
        };
        this._notify(Object.freeze({ ...this._state }), Object.freeze({ ...INITIAL_STATE }));
    }
}

export const store = new Store();
