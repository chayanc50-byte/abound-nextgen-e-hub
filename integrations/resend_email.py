import os
import requests
from flask import current_app

RESEND_API_URL = "https://api.resend.com/emails"


def send_email(to, subject, html):
    api_key = os.environ.get("RESEND_API_KEY")

    if not api_key:
        current_app.logger.error("RESEND_API_KEY is not configured.")
        return False

    payload = {
        "from": os.environ.get(
            "MAIL_FROM",
            "Abound Next-Gen E-Hub <noreply@aboundehub.com>"
        ),
        "to": to if isinstance(to, list) else [to],
        "subject": subject,
        "html": html,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            RESEND_API_URL,
            json=payload,
            headers=headers,
            timeout=20,
        )

        if response.ok:
            current_app.logger.info(f"Email sent successfully to {to}")
            return True

        current_app.logger.error(
            f"Resend Error {response.status_code}: {response.text}"
        )
        return False

    except Exception as e:
        current_app.logger.exception(
            f"Failed to send email: {e}"
        )
        return False