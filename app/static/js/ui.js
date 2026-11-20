/*
 * UI shell behaviour only: sidebar collapse (desktop), slide-out drawer
 * (mobile) and visual feedback for overlay upload zones.
 * Contains no generation, upload or API logic.
 */
(function () {
    "use strict";

    var root = document.documentElement;
    var STORAGE_KEY = "studio.sidebar";
    var mobileQuery = window.matchMedia("(max-width: 960px)");

    var sidebar = document.getElementById("sidebar");
    var backdrop = document.querySelector(".sidebar-backdrop");
    var openButton = document.querySelector("[data-sidebar-open]");
    var collapseButton = document.querySelector("[data-sidebar-collapse]");
    var closeButtons = document.querySelectorAll("[data-sidebar-close]");

    function store(value) {
        try { localStorage.setItem(STORAGE_KEY, value); } catch (e) { /* storage unavailable */ }
    }

    /* ---------- Desktop collapse ---------- */

    function syncCollapseButton() {
        if (!collapseButton) return;
        var collapsed = root.classList.contains("sidebar-collapsed");
        var label = collapsed ? "Expand sidebar" : "Collapse sidebar";
        collapseButton.setAttribute("aria-expanded", String(!collapsed));
        collapseButton.setAttribute("title", label);
        collapseButton.setAttribute("aria-label", label);
        var text = collapseButton.querySelector(".collapse-label");
        if (text) text.textContent = collapsed ? "Expand" : "Collapse";
    }

    if (collapseButton) {
        collapseButton.addEventListener("click", function () {
            var collapsed = !root.classList.contains("sidebar-collapsed");
            root.classList.toggle("sidebar-collapsed", collapsed);
            store(collapsed ? "collapsed" : "expanded");
            syncCollapseButton();
        });
        syncCollapseButton();
    }

    /* ---------- Mobile drawer ---------- */

    function isDrawerOpen() {
        return root.classList.contains("sidebar-open");
    }

    function openDrawer() {
        root.classList.add("sidebar-open");
        if (backdrop) backdrop.hidden = false;
        if (openButton) openButton.setAttribute("aria-expanded", "true");
        var firstLink = sidebar && sidebar.querySelector(".nav-link");
        if (firstLink) firstLink.focus({ preventScroll: true });
    }

    function closeDrawer(restoreFocus) {
        if (!isDrawerOpen()) return;
        root.classList.remove("sidebar-open");
        if (backdrop) backdrop.hidden = true;
        if (openButton) {
            openButton.setAttribute("aria-expanded", "false");
            if (restoreFocus) openButton.focus({ preventScroll: true });
        }
    }

    if (openButton) {
        openButton.addEventListener("click", function () {
            isDrawerOpen() ? closeDrawer(true) : openDrawer();
        });
    }

    Array.prototype.forEach.call(closeButtons, function (button) {
        button.addEventListener("click", function () { closeDrawer(true); });
    });

    if (sidebar) {
        sidebar.addEventListener("click", function (event) {
            if (mobileQuery.matches && event.target.closest("a.nav-link")) {
                closeDrawer(false);
            }
        });
    }

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && isDrawerOpen()) closeDrawer(true);
    });

    function handleViewportChange() {
        if (!mobileQuery.matches) closeDrawer(false);
    }

    if (mobileQuery.addEventListener) {
        mobileQuery.addEventListener("change", handleViewportChange);
    } else if (mobileQuery.addListener) {
        mobileQuery.addListener(handleViewportChange);
    }

    /* ---------- Overlay upload zones (visual feedback only) ---------- */

    Array.prototype.forEach.call(document.querySelectorAll("[data-dropzone]"), function (zone) {
        var input = zone.querySelector('input[type="file"]');
        var filename = zone.querySelector("[data-dropzone-filename]");
        var emptyText = filename ? filename.textContent : "";

        if (!input) return;

        input.addEventListener("change", function () {
            var file = input.files && input.files[0];
            zone.classList.toggle("has-file", Boolean(file));
            if (filename) filename.textContent = file ? file.name : emptyText;
        });

        // Highlight only; the native file input receives the drop itself.
        ["dragenter", "dragover"].forEach(function (name) {
            zone.addEventListener(name, function () { zone.classList.add("dragging"); });
        });
        ["dragleave", "drop"].forEach(function (name) {
            zone.addEventListener(name, function () { zone.classList.remove("dragging"); });
        });
    });
})();
