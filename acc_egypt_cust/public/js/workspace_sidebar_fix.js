/**
 * workspace_sidebar_fix.js
 * ========================
 * Custom app: acc_egypt_cust
 * Frappe version: 16.x
 *
 * PROBLEM
 * -------
 * In Frappe v16, every URL navigation fires:
 *
 *   frappe.router.route()
 *     → router.trigger("change")
 *       → frappe.app.sidebar.set_workspace_sidebar(router)   [sidebar.js:327]
 *         → this.resolve_sidebar(entity, module)             [sidebar.js:660]
 *           → frappe.app.sidebar.setup(target)              [sidebar.js:677]
 *
 * `resolve_sidebar` scans all workspace_sidebar_item entries to find which
 * sidebar contains a link to the navigated DocType.  When it finds, for
 * example, "Stock" has "Item", it calls setup("Stock") — overwriting our
 * custom workspace sidebar الحسابات.
 *
 * FIX
 * ---
 * We override `frappe.ui.Sidebar.prototype.set_workspace_sidebar` so that it
 * NO LONGER auto-switches the sidebar on route change.
 *
 * What we keep:
 *   - set_active_workspace_item()  — still highlights the active link in the
 *     current sidebar (so the UX indicator still works).
 *
 * What we remove:
 *   - The call to frappe.app.sidebar.setup(target) triggered by route changes.
 *
 * Explicit workspace switches (user clicks a different workspace in the sidebar
 * header dropdown or navigates directly to a Workspace URL) are handled by
 * frappe.views.Workspace.show_page → this.sidebar.setup(...), which calls
 * setup() directly — that path is NOT touched here, so explicit switching
 * still works.
 *
 * localStorage key: "sidebar_pinned_workspace"
 *   Written when the user explicitly navigates to a Workspace page.
 *   Read on page load to restore the last pinned workspace.
 */

(function () {
    "use strict";

    // -------------------------------------------------------------------------
    // Helper: wait for frappe.app.sidebar to be available before patching.
    // sidebar is created inside frappe.Application.startup() → make_sidebar()
    // which runs synchronously before "app_ready", so by the time the event
    // fires the instance already exists.
    // -------------------------------------------------------------------------
    function applyPatch() {
        if (
            !frappe ||
            !frappe.ui ||
            !frappe.ui.Sidebar ||
            !frappe.app ||
            !frappe.app.sidebar
        ) {
            // Retry in 100 ms — should never be needed, but just in case
            setTimeout(applyPatch, 100);
            return;
        }

        // ------------------------------------------------------------------
        // 1.  Pin the sidebar whenever the user explicitly opens a Workspace.
        //     We do this by wrapping the prototype `setup` method so that
        //     every call to setup() that originates from a Workspace route
        //     persists the choice to localStorage.
        //
        //     Note: setup() is also called by set_workspace_sidebar (the
        //     auto-switch we want to block), so we track WHO is calling it
        //     via the _allow_setup flag set only by our Workspace navigation
        //     hook.
        // ------------------------------------------------------------------

        const _original_setup = frappe.ui.Sidebar.prototype.setup;

        /**
         * Wrapped setup() — same signature as the original.
         * Stores the explicit workspace title to localStorage so we can
         * restore it across page loads.
         *
         * @param {string} workspace_title
         */
        frappe.ui.Sidebar.prototype.setup = function (workspace_title) {
            // Persist the explicitly chosen workspace so the next page load
            // can restore it instead of auto-resolving.
            if (workspace_title) {
                localStorage.setItem("sidebar_pinned_workspace", workspace_title);
            }

            // Call the original setup (renders sidebar items, header, etc.)
            _original_setup.call(this, workspace_title);
        };

        // ------------------------------------------------------------------
        // 2.  Override set_workspace_sidebar — the method called on EVERY
        //     router "change" event.  We replace it entirely:
        //
        //     NEW behaviour:
        //       a) If the current route IS a Workspace (e.g. /desk/الحسابات),
        //          we allow setup() to run so the sidebar reflects that page.
        //       b) For any other route (List, Form, Report, …), we DO NOT
        //          switch the sidebar — we only highlight the active link.
        // ------------------------------------------------------------------

        /**
         * Replaces frappe.ui.Sidebar.prototype.set_workspace_sidebar
         *
         * Original behaviour (blocked):
         *   Resolves which workspace sidebar matches the current route and
         *   switches to it unconditionally.
         *
         * New behaviour:
         *   - Workspace routes  → allow the sidebar to switch (user navigated
         *     explicitly to another Workspace).
         *   - All other routes  → keep the current sidebar; only refresh the
         *     active-item highlight.
         *
         * @param {object} router  - frappe.router instance passed by the
         *                           "change" event (may be undefined on manual
         *                           calls from refresh()).
         */
        frappe.ui.Sidebar.prototype.set_workspace_sidebar = function (router) {
            try {
                const route = frappe.get_route();

                // route[0] === "Workspaces" means the user navigated directly
                // to a Workspace page (e.g. clicked the workspace name in
                // breadcrumbs, or typed /desk/الحسابات in the URL).
                const is_workspace_route = route && route[0] === "Workspaces";

                if (is_workspace_route) {
                    // Determine which workspace name is being shown.
                    // route = ["Workspaces", "WorkspaceName"]   (public)
                    // route = ["Workspaces", "private", "Name"] (private)
                    const ws_name =
                        route[1] === "private" ? route[2] : route[1];

                    if (ws_name && ws_name !== this.sidebar_title) {
                        // Explicit workspace navigation → allow the switch.
                        // setup() will also persist the choice to localStorage.
                        frappe.app.sidebar.setup(ws_name);
                    }
                }
                // For ALL non-workspace routes (List, Form, Report, Tree, …)
                // we intentionally do NOT call setup(). The sidebar stays on
                // whichever workspace the user last explicitly opened.

            } catch (e) {
                console.error("[workspace_sidebar_fix] set_workspace_sidebar error:", e);
            }

            // Always refresh the active-item highlight so the current page
            // is visually indicated in the sidebar even without switching.
            this.set_active_workspace_item();
        };

        // ------------------------------------------------------------------
        // 3.  On startup: restore the pinned workspace if one was saved.
        //     This ensures that after a page refresh the user sees the same
        //     sidebar they had before, rather than whatever Frappe auto-
        //     resolves from the current URL.
        // ------------------------------------------------------------------
        const pinned = localStorage.getItem("sidebar_pinned_workspace");
        if (
            pinned &&
            frappe.boot.workspace_sidebar_item &&
            frappe.boot.workspace_sidebar_item[pinned.toLowerCase()] &&
            frappe.app.sidebar.sidebar_title !== pinned
        ) {
            // Use the wrapped setup() — it will persist again (idempotent).
            frappe.app.sidebar.setup(pinned);
        }

        console.log(
            "[acc_egypt_cust] workspace_sidebar_fix applied on Frappe",
            frappe.__version__ || "(version unknown)"
        );
    }

    // -------------------------------------------------------------------------
    // Entry point: wait for the app to be fully ready, then apply the patch.
    // "app_ready" is triggered at the end of frappe.Application.startup().
    // -------------------------------------------------------------------------
    $(document).on("app_ready", function () {
        applyPatch();
    });
})();
