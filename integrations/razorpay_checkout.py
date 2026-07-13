"""Razorpay Standard Checkout helpers."""
from __future__ import annotations

import hashlib
import hmac
from typing import Any


def get_razorpay_client(key_id: str, key_secret: str):
    import razorpay

    return razorpay.Client(auth=(key_id, key_secret))


def create_razorpay_order(client, amount: int, currency: str, receipt: str) -> dict[str, Any]:
    return client.order.create(
        {
            "amount": amount,
            "currency": currency,
            "receipt": receipt,
        }
    )


def verify_payment_signature(key_secret: str, order_id: str, payment_id: str, signature: str) -> bool:
    body = f"{order_id}|{payment_id}"
    expected = hmac.new(
        key_secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
