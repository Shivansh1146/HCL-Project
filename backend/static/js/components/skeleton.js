/**
 * skeleton.js — Skeleton Loading Placeholder Component.
 *
 * Usage:
 *   Skeleton.card()          → glass card placeholder
 *   Skeleton.row(width)      → single horizontal bar
 *   Skeleton.repoCard()      → repository card placeholder
 */

export const Skeleton = {
    row(width = "100%", height = "1rem") {
        const el = document.createElement("div");
        el.className = "skeleton";
        el.style.cssText = `width:${width};height:${height};margin-bottom:0.5rem;`;
        el.setAttribute("aria-hidden", "true");
        return el;
    },

    card() {
        const el = document.createElement("div");
        el.className = "glass-card";
        el.setAttribute("aria-hidden", "true");
        el.appendChild(this.row("40%", "0.85rem"));
        el.appendChild(this.row("70%", "2.5rem"));
        el.appendChild(this.row("55%", "0.75rem"));
        return el;
    },

    repoCard() {
        const el = document.createElement("div");
        el.className = "glass-card";
        el.setAttribute("aria-hidden", "true");
        el.style.display = "flex";
        el.style.alignItems = "center";
        el.style.gap = "1rem";

        const avatar = document.createElement("div");
        avatar.className = "skeleton";
        avatar.style.cssText = "width:44px;height:44px;border-radius:10px;flex-shrink:0;";

        const lines = document.createElement("div");
        lines.style.flex = "1";
        lines.appendChild(this.row("60%", "0.9rem"));
        lines.appendChild(this.row("40%", "0.75rem"));

        el.appendChild(avatar);
        el.appendChild(lines);
        return el;
    },

    /**
     * Renders n skeleton placeholders into a container.
     */
    fill(containerEl, count = 4, type = "card") {
        containerEl.innerHTML = "";
        for (let i = 0; i < count; i++) {
            containerEl.appendChild(this[type]());
        }
    }
};
/**
 * String-based skeleton markup for template literals.
 *
 * Dashboard and list pages render their initial loading state with innerHTML,
 * so they need markup rather than the DOM nodes returned by Skeleton.card().
 */
export function renderSkeleton(type = "card") {
    if (type === "row") {
        return '<div class="skeleton" aria-hidden="true" style="width:100%;height:1rem;margin-bottom:0.5rem;"></div>';
    }

    if (type === "repoCard") {
        return `
            <div class="glass-card" aria-hidden="true" style="display:flex;align-items:center;gap:1rem;">
                <div class="skeleton" style="width:44px;height:44px;border-radius:10px;flex-shrink:0;"></div>
                <div style="flex:1;">
                    <div class="skeleton" style="width:60%;height:0.9rem;margin-bottom:0.5rem;"></div>
                    <div class="skeleton" style="width:40%;height:0.75rem;"></div>
                </div>
            </div>
        `;
    }

    return `
        <div class="glass-card" aria-hidden="true">
            <div class="skeleton" style="width:40%;height:0.85rem;margin-bottom:0.5rem;"></div>
            <div class="skeleton" style="width:70%;height:2.5rem;margin-bottom:0.5rem;"></div>
            <div class="skeleton" style="width:55%;height:0.75rem;"></div>
        </div>
    `;
}
