import os
import requests

RESEND_API_URL = "https://api.resend.com/emails"


def send_email(to, subject, html):
    api_key = os.environ.get("RESEND_API_KEY")

    if not api_key:
        print("RESEND_API_KEY is not configured.")
        return False

    payload = {
        "from": os.environ.get(
            "MAIL_FROM",
            "noreply@aboundehub.com"
        ),
       "to": to if isinstance(to, list) else [to],
        "subject": subject,
        "html": html,
    

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        RESEND_API_URL,
        json=payload,
        headers=headers,
        timeout=20,
    )

    if response.status_code in (200, 202):
        return True

    print("Resend Error")
    print(response.status_code)
    print(response.text)

    return False