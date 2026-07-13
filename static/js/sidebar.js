(function() {
    // Accordion: only one menu open at a time
    document.querySelectorAll('.sidebar-accordion').forEach(function(acc) {
        var toggle = acc.querySelector('.accordion-toggle');
        var content = acc.querySelector('.accordion-content');
        if (!toggle || !content) return;

        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            var wasOpen = acc.classList.contains('open');
            document.querySelectorAll('.sidebar-accordion').forEach(function(other) {
                other.classList.remove('open');
            });
            if (!wasOpen) {
                acc.classList.add('open');
            }
        });
    });

    // Open accordion that contains active item on load
    var activeAccordion = document.querySelector('.sidebar-accordion .accordion-toggle.active, .sidebar-accordion .sidebar-subitem.active');
    if (activeAccordion) {
        var acc = activeAccordion.closest('.sidebar-accordion');
        if (acc) {
            document.querySelectorAll('.sidebar-accordion').forEach(function(other) {
                other.classList.remove('open');
            });
            acc.classList.add('open');
        }
    }

    // Hamburger toggle
    var sidebar = document.getElementById('app-sidebar');
    var main = document.querySelector('.app-main, .admin-main');
    var hamburger = document.getElementById('hamburger-btn');
    var overlay = document.getElementById('sidebar-overlay');

    if (!sidebar || !main || !hamburger || !overlay) return;

    function isMobile() {
        return window.matchMedia && window.matchMedia('(max-width: 992px)').matches;
    }

    function closeSidebar() {
        sidebar.classList.add('sidebar-closed');
        main.classList.add('sidebar-closed');
        overlay.classList.remove('active');
    }

    function openSidebar() {
        sidebar.classList.remove('sidebar-closed');
        main.classList.remove('sidebar-closed');
        if (isMobile()) {
            overlay.classList.add('active');
        }
    }

    function toggleSidebar() {
        var closed = sidebar.classList.contains('sidebar-closed');
        if (closed) {
            openSidebar();
        } else {
            closeSidebar();
        }
    }

    hamburger.addEventListener('click', toggleSidebar);
    overlay.addEventListener('click', closeSidebar);

    // Mobile: start closed. Desktop: start open.
    if (isMobile()) {
        closeSidebar();
    }

    // Handle resize
    window.addEventListener('resize', function() {
        if (!isMobile()) {
            overlay.classList.remove('active');
            sidebar.classList.remove('sidebar-closed');
            main.classList.remove('sidebar-closed');
        } else if (!sidebar.classList.contains('sidebar-closed')) {
            overlay.classList.add('active');
        }
    });
})();
