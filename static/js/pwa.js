/* Abound NextGen E Hub - PWA: Service Worker + Install Prompt */
(function() {
    var deferredPrompt;
    var installBanner = document.getElementById('pwa-install-banner');
    var installBtn = document.getElementById('pwa-install-btn');
    var dismissBtn = document.getElementById('pwa-install-dismiss');
    var BANNER_DISMISSED_KEY = 'pwa_install_dismissed';
    var BANNER_DAYS = 7;

    function shouldShowBanner() {
        if (!installBanner) return false;
        if (window.matchMedia('(display-mode: standalone)').matches) return false;
        if (window.navigator.standalone) return false;
        var dismissed = localStorage.getItem(BANNER_DISMISSED_KEY);
        if (dismissed) {
            var t = parseInt(dismissed, 10);
            if (Date.now() - t < BANNER_DAYS * 24 * 60 * 60 * 1000) return false;
        }
        return true;
    }

    function showBanner() {
        if (installBanner && shouldShowBanner()) {
            installBanner.style.display = 'block';
            installBanner.setAttribute('aria-hidden', 'false');
        }
    }

    function hideBanner() {
        if (installBanner) {
            installBanner.style.display = 'none';
            installBanner.setAttribute('aria-hidden', 'true');
        }
        localStorage.setItem(BANNER_DISMISSED_KEY, String(Date.now()));
    }

    window.addEventListener('beforeinstallprompt', function(e) {
        e.preventDefault();
        deferredPrompt = e;
        showBanner();
    });

    if (installBtn) {
        installBtn.addEventListener('click', function() {
            if (deferredPrompt) {
                deferredPrompt.prompt();
                deferredPrompt.userChoice.then(function(choice) {
                    if (choice.outcome === 'accepted') hideBanner();
                    deferredPrompt = null;
                });
            } else {
                hideBanner();
            }
        });
    }
    if (dismissBtn) dismissBtn.addEventListener('click', hideBanner);

    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/service-worker.js', { scope: '/' })
            .then(function(reg) { /* registered */ })
            .catch(function(err) { console.warn('SW registration failed:', err); });
    }
})();
