// Main JavaScript file for common functionality

// Floating header scroll effect (homepage & login)
document.addEventListener('DOMContentLoaded', function() {
    var body = document.body;
    if (body.classList.contains('public-homepage') || body.classList.contains('public-login')) {
        function onScroll() {
            if (window.scrollY > 30) {
                body.classList.add('scrolled');
            } else {
                body.classList.remove('scrolled');
            }
        }
        window.addEventListener('scroll', onScroll, { passive: true });
        onScroll();
    }
});

// Public hamburger menu toggle (homepage, login, products, etc.)
document.addEventListener('DOMContentLoaded', function() {
    var hamburger = document.getElementById('publicHamburger');
    var sidebar = document.getElementById('publicSidebar');
    var overlay = document.getElementById('publicSidebarOverlay');

    function openPublicMenu() {
        if (sidebar) sidebar.classList.add('is-open');
        if (overlay) overlay.classList.add('is-open');
        if (overlay) overlay.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
    }
    function closePublicMenu() {
        if (sidebar) sidebar.classList.remove('is-open');
        if (overlay) overlay.classList.remove('is-open');
        if (overlay) overlay.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
    }

    if (hamburger) hamburger.addEventListener('click', openPublicMenu);
    if (overlay) overlay.addEventListener('click', closePublicMenu);

    if (sidebar) {
        sidebar.querySelectorAll('.public-sidebar-link').forEach(function(link) {
            link.addEventListener('click', closePublicMenu);
        });
    }

    // Floating label support (for password fields and cross-browser)
    document.querySelectorAll('.form-float input, .form-float textarea').forEach(function(input) {
        function updateLabel() {
            input.classList.toggle('filled', input.value.length > 0);
        }
        input.addEventListener('input', updateLabel);
        input.addEventListener('change', updateLabel);
        input.addEventListener('blur', updateLabel);
        updateLabel(); // init on load (e.g. browser autofill)
    });
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(function(message) {
        setTimeout(function() {
            message.style.transition = 'opacity 0.5s';
            message.style.opacity = '0';
            setTimeout(function() {
                message.remove();
            }, 500);
        }, 5000);
    });
});

// Utility function for API calls
async function apiCall(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        return await response.json();
    } catch (error) {
        console.error('API call error:', error);
        throw error;
    }
}
