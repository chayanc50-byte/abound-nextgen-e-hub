/**
 * Razorpay Standard Checkout for checkout.html
 * Expects window.CHECKOUT_CONFIG from the template.
 */
(function () {
    function showError(msg) {
        var el = document.getElementById('razorpay-error');
        if (el) {
            el.textContent = msg;
            el.style.display = 'block';
        } else {
            alert(msg);
        }
    }

    function clearError() {
        var el = document.getElementById('razorpay-error');
        if (el) {
            el.textContent = '';
            el.style.display = 'none';
        }
    }

    function setPayButtonLoading(loading) {
        var btn = document.getElementById('place-order-btn');
        if (!btn) return;
        var text = btn.querySelector('.btn-text');
        var loadingEl = btn.querySelector('.btn-loading');
        if (loading) {
            if (text) text.style.display = 'none';
            if (loadingEl) loadingEl.style.display = 'inline-flex';
            btn.disabled = true;
        } else {
            if (text) text.style.display = '';
            if (loadingEl) loadingEl.style.display = 'none';
            btn.disabled = false;
        }
    }

    window.startRazorpayCheckout = function (form) {
        clearError();
        var cfg = window.CHECKOUT_CONFIG || {};
        if (!cfg.razorpayKeyId) {
            showError('Payment is not configured. Please contact support.');
            return;
        }
        if (typeof Razorpay === 'undefined') {
            showError('Payment script failed to load. Please refresh and try again.');
            return;
        }

        setPayButtonLoading(true);
        var formData = new FormData(form);

        fetch('/api/checkout/prepare-pending', {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
            .then(function (r) {
                return r.json().then(function (data) {
                    return { ok: r.ok, status: r.status, data: data };
                });
            })
            .then(function (res) {
                if (!res.ok) {
                    throw new Error((res.data && res.data.error) || 'Could not prepare order.');
                }
                return res.data;
            })
            .then(function (pending) {
                return fetch('/api/create-order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        amount: pending.amount_paise,
                        currency: 'INR',
                        receipt: pending.receipt,
                    }),
                }).then(function (r) {
                    return r.json().then(function (data) {
                        return { ok: r.ok, status: r.status, data: data, pending: pending };
                    });
                });
            })
            .then(function (res) {
                if (!res.ok) {
                    var msg = (res.data && res.data.error) || 'Could not create payment order.';
                    throw new Error(msg);
                }
                openRazorpayModal(res.data, res.pending);
            })
            .catch(function (err) {
                showError(err.message || 'Payment could not be started.');
                setPayButtonLoading(false);
                if (typeof window.updateCheckoutFormState === 'function') {
                    window.updateCheckoutFormState();
                }
            });
    };

    function openRazorpayModal(rzpOrder, pending) {
        var cfg = window.CHECKOUT_CONFIG || {};
        var options = {
            key: cfg.razorpayKeyId,
            amount: rzpOrder.amount,
            currency: rzpOrder.currency,
            name: cfg.businessName || 'Abound NextGen E Hub',
            description: pending.product_name || 'Order payment',
            order_id: rzpOrder.order_id,
            prefill: {
                name: cfg.userName || '',
                email: cfg.userEmail || '',
                contact: cfg.userPhone || '',
            },
            theme: { color: '#ff7a00' },
            handler: function (response) {
                verifyPayment(response, pending.app_order_id);
            },
            modal: {
                ondismiss: function () {
                    showError('Payment cancelled.');
                    setPayButtonLoading(false);
                    if (typeof window.updateCheckoutFormState === 'function') {
                        window.updateCheckoutFormState();
                    }
                },
            },
        };

        var rzp = new Razorpay(options);
        rzp.on('payment.failed', function (response) {
            var reason =
                (response.error && response.error.description) ||
                (response.error && response.error.reason) ||
                'Payment failed. Please try again.';
            showError(reason);
            setPayButtonLoading(false);
            if (typeof window.updateCheckoutFormState === 'function') {
                window.updateCheckoutFormState();
            }
        });
        rzp.open();
        setPayButtonLoading(false);
    }

    function verifyPayment(response, appOrderId) {
        setPayButtonLoading(true);
        clearError();
        fetch('/api/verify-payment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_order_id: response.razorpay_order_id,
                razorpay_signature: response.razorpay_signature,
                app_order_id: appOrderId,
            }),
        })
            .then(function (r) {
                return r.json().then(function (data) {
                    return { ok: r.ok, data: data };
                });
            })
            .then(function (res) {
                if (!res.ok || !res.data.success) {
                    throw new Error((res.data && res.data.error) || 'Payment verification failed.');
                }
                window.location.href =
                    '/order-success?order_id=' + encodeURIComponent(res.data.app_order_id);
            })
            .catch(function (err) {
                showError(err.message || 'Payment verification failed.');
                setPayButtonLoading(false);
                if (typeof window.updateCheckoutFormState === 'function') {
                    window.updateCheckoutFormState();
                }
            });
    }
})();
