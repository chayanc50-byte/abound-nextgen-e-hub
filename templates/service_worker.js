/* Abound NextGen E Hub - Service Worker (caching + FCM) */
const CACHE_NAME = 'abound-ehub-v2';

const STATIC_ASSETS = [
  '/static/css/style.css',
  '/static/js/main.js',
  '/static/js/sidebar.js',
  '/static/js/pwa.js',
  '/static/images/icon-192.png',
  '/static/images/icon-512.png',
  '/static/images/logo.png',
  '/offline'
];

self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(STATIC_ASSETS.map(function(url) {
        return new Request(url, { cache: 'reload' });
      })).catch(function(err) {
        console.warn('SW pre-cache partial:', err);
      });
    }).then(function() {
      return self.skipWaiting();
    })
  );
});

self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames.filter(function(name) { return name !== CACHE_NAME; })
          .map(function(name) { return caches.delete(name); })
      );
    }).then(function() { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function(event) {
  var url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    caches.match(event.request).then(function(cached) {
      if (cached) return cached;
      return fetch(event.request).then(function(response) {
        var contentType = response.headers.get('content-type') || '';
        var cacheable = /\.(css|js|png|jpg|jpeg|gif|webp|ico|woff2?)$/i.test(url.pathname) ||
          contentType.includes('text/css') || contentType.includes('application/javascript');
        if (cacheable && response.ok) {
          var r = response.clone();
          caches.open(CACHE_NAME).then(function(cache) { cache.put(event.request, r); });
        }
        return response;
      }).catch(function() {
        if (event.request.mode === 'navigate') {
          return caches.match('/offline').then(function(offline) {
            return offline || new Response(
              '<!DOCTYPE html><html><body><h1>Offline</h1><p>Please check your connection.</p></body></html>',
              { headers: { 'Content-Type': 'text/html' } }
            );
          });
        }
        throw new Error('Offline');
      });
    })
  );
});

{% if firebase_enabled %}
/* Firebase Cloud Messaging */
importScripts('https://www.gstatic.com/firebasejs/10.7.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.7.0/firebase-messaging-compat.js');
firebase.initializeApp({{ firebase_config | tojson }});
var messaging = firebase.messaging();
messaging.onBackgroundMessage(function(payload) {
  var notif = payload.notification || {};
  var title = notif.title || 'Notification';
  var body = notif.body || '';
  var icon = notif.icon || '{{ icon_url }}';
  var data = payload.data || {};
  var url = data.url || data.click_action || notif.click_action || '/';
  var fullUrl = url.startsWith('http') ? url : self.location.origin + (url.startsWith('/') ? url : '/' + url);
  return self.registration.showNotification(title, {
    body: body,
    icon: icon,
    data: { url: fullUrl },
    tag: data.tag || 'abound-' + Date.now()
  });
});
self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  var url = event.notification.data && event.notification.data.url;
  if (!url) url = self.location.origin + '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
      for (var i = 0; i < clientList.length; i++) {
        var c = clientList[i];
        if (c.url && 'focus' in c) { c.navigate(url); return c.focus(); }
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
{% endif %}
