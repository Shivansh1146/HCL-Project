/**
 * dom.js — XSS-safe DOM utilities.
 *
 * Rule: NEVER use innerHTML with user data.
 *       All user content must pass through dom.escape() first.
 */

export const dom = {
    /**
     * Escapes a string for safe HTML text injection.
     * Prevents XSS when interpolating user data into innerHTML templates.
     */
    escape(str) {
        if (str === null || str === undefined) return "";
        const div = document.createElement("div");
        div.textContent = String(str);
        return div.innerHTML;
    },

    /**
     * Validates and sanitizes a URL, only allowing http/https schemes.
     * Falls back to "#" for any suspicious URL.
     */
    safeUrl(url) {
        if (!url) return "#";
        try {
            const parsed = new URL(url, window.location.origin);
            if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return "#";
            return parsed.href;
        } catch {
            return "#";
        }
    },

    /**
     * Programmatic element factory — safer than innerHTML for dynamic content.
     */
    createElement(tag, options = {}) {
        const el = document.createElement(tag);
        if (options.className) el.className = options.className;
        if (options.id)        el.id = options.id;
        if (options.text)      el.textContent = options.text;   // Always safe

        if (options.attrs) {
            Object.entries(options.attrs).forEach(([k, v]) => {
                // Prevent setting dangerous attributes
                if (/^on/i.test(k)) return;
                el.setAttribute(k, v);
            });
        }
        if (options.events) {
            Object.entries(options.events).forEach(([event, handler]) =>
                el.addEventListener(event, handler)
            );
        }
        if (options.children) {
            options.children.forEach(child => {
                if (typeof child === "string") {
                    el.appendChild(document.createTextNode(child));
                } else if (child instanceof Node) {
                    el.appendChild(child);
                }
            });
        }
        return el;
    },

    qs(selector, scope = document)  { return scope.querySelector(selector); },
    qsa(selector, scope = document) { return Array.from(scope.querySelectorAll(selector)); }
};
