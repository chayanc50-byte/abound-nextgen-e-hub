/**
 * Firebase Cloud Messaging - Push Notifications
 * Abound NextGen E Hub PWA
 */
(function() {
  'use strict';

  function getNotSupportedReason() {
    if (typeof window === 'undefined') return 'Unavailable';
    if (!('Notification' in window)) return 'Your browser does not support notifications.';
    if (!('serviceWorker' in navigator)) return 'Service workers not available.';
    if (typeof window.isSecureContext === 'boolean' && !window.isSecureContext) {
      return 'Push notifications require HTTPS. Open this app via https:// or localhost. If testing on a phone, use Chrome and ensure the URL starts with https:// (e.g. via ngrok or your deployed domain).';
    }
    return null;
  }

  var reason = getNotSupportedReason();
  window.AboundPush = {
    supported: !reason,
    notSupportedReason: reason,
    enabled: false,
    token: null,

    init: function() {
      if (!this.supported) return Promise.resolve();
      return this.checkConfig().then(function(ok) {
        if (!ok) return;
        return window.AboundPush.requestPermissionAndRegister();
      }).catch(function(err) {
        console.warn('Push init:', err);
      });
    },

    checkConfig: function() {
      return fetch('/api/firebase-config')
        .then(function(r) { return r.json(); })
        .then(function(cfg) {
          if (!cfg || !cfg.apiKey || !cfg.vapidKey || !cfg.messagingSenderId) {
            return false;
          }
          window.__FIREBASE_PUSH_CONFIG__ = cfg;
          return true;
        })
        .catch(function() { return false; });
    },

    requestPermissionAndRegister: function() {
      var self = this;
      if (!window.__FIREBASE_PUSH_CONFIG__) {
        return this.checkConfig().then(function(ok) {
          if (!ok) return null;
          return self._doRegister();
        });
      }
      return this._doRegister();
    },

    _doRegister: function() {
      var self = this;
      return Notification.requestPermission().then(function(perm) {
        if (perm !== 'granted') return null;
        self.enabled = true;
        return self._getToken();
      });
    },

    _getToken: function() {
      var self = this;
      var cfg = window.__FIREBASE_PUSH_CONFIG__;
      if (!cfg) return Promise.resolve(null);

      return new Promise(function(resolve, reject) {
        if (typeof firebase === 'undefined') {
          reject(new Error('Firebase SDK not loaded'));
          return;
        }
        try {
          if (!firebase.apps || !firebase.apps.length) {
            firebase.initializeApp({ apiKey: cfg.apiKey, projectId: cfg.projectId, appId: cfg.appId, messagingSenderId: cfg.messagingSenderId, storageBucket: cfg.storageBucket, authDomain: cfg.authDomain });
          }
        } catch (e) { /* already init */ }
        var messaging = firebase.messaging();
        navigator.serviceWorker.getRegistration('/').then(function(reg) {
          if (!reg) return navigator.serviceWorker.register('/service-worker.js', { scope: '/' });
          return reg;
        }).then(function(reg) {
          return messaging.getToken({
            vapidKey: cfg.vapidKey,
            serviceWorkerRegistration: reg
          });
        }).then(function(token) {
          self.token = token;
          resolve(token);
        }).catch(reject);
      });
    },

    enable: function() {
      var self = this;
      if (!this.supported) {
        return Promise.reject(new Error('Push notifications not supported'));
      }
      return this.requestPermissionAndRegister().then(function(token) {
        if (!token) return null;
        return fetch('/api/save-device-token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
          body: JSON.stringify({ device_token: token })
        }).then(function(r) { return r.json(); }).then(function(data) {
          if (data.success) {
            self.enabled = true;
            return true;
          }
          return false;
        });
      });
    },

    disable: function(removeAll) {
      var self = this;
      var payload = removeAll ? { remove_all: true } : { device_token: this.token };
      if (!removeAll && !this.token) return Promise.resolve(true);
      return fetch('/api/remove-device-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify(payload)
      }).then(function(r) { return r.json(); }).then(function(data) {
        if (data.success) {
          self.token = null;
          self.enabled = false;
          return true;
        }
        return false;
      });
    },

    hasToken: function() {
      return !!this.token;
    }
  };
})();
