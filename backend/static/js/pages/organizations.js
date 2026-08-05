/**
 * pages/organizations.js — Organizations page stub.
 */
import { store } from "../utils/state.js";
import { dom }   from "../utils/dom.js";

export async function renderOrganizationsPage(outlet) {
    const { organizations } = store.getState();

    outlet.innerHTML = `
        <div class="animate-fade-up" style="padding:2rem 0;">
            <h1 style="font-size:1.75rem;font-weight:800;letter-spacing:-0.03em;margin-bottom:0.4rem;">Organizations</h1>
            <p style="color:var(--text-secondary);font-size:0.95rem;margin-bottom:2.5rem;">Connected GitHub Organizations & Team Workspaces.</p>

            <div class="grid-12">
                ${organizations && organizations.length > 0 ? organizations.map(org => `
                    <div class="glass-card col-span-4" style="display:flex;align-items:center;gap:1rem;">
                        <div style="width:42px;height:42px;border-radius:10px;background:rgba(59,130,246,0.15);color:var(--primary);display:flex;align-items:center;justify-content:center;font-weight:700;">
                            ${dom.escape(org.charAt(0).toUpperCase())}
                        </div>
                        <div>
                            <h3 style="font-size:1rem;font-weight:600;">${dom.escape(org)}</h3>
                            <span class="badge badge-success" style="font-size:0.7rem;margin-top:0.25rem;">Active</span>
                        </div>
                    </div>
                `).join("") : `
                    <div class="glass-card col-span-12" style="text-align:center;padding:3rem 2rem;">
                        <p style="color:var(--text-muted);">No organization memberships detected. Operating under Personal account.</p>
                    </div>
                `}
            </div>
        </div>
    `;
}
