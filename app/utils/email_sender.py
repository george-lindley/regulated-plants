import requests


class EmailDeliveryError(RuntimeError):
    pass


def _config_timeout(config) -> int:
    return max(1, int(config.get("EMAIL_SEND_TIMEOUT_SECONDS", 8) or 8))


def _sender(config) -> str:
    return config.get("MAIL_DEFAULT_SENDER") or ""


def _send_postmark(config, subject: str, recipients: list, body: str, reply_to: str = None, html_body: str = None):
    token = config.get("POSTMARK_SERVER_TOKEN")
    sender = _sender(config)
    timeout = _config_timeout(config)
    api_url = config.get("POSTMARK_API_URL") or "https://api.postmarkapp.com/email"
    message_stream = config.get("POSTMARK_MESSAGE_STREAM") or "outbound"

    if not token or not sender:
        raise EmailDeliveryError("Postmark email is not configured")

    payload = {
        "From": sender,
        "To": ", ".join(recipients),
        "Subject": subject,
        "TextBody": body,
        "MessageStream": message_stream,
    }
    if html_body:
        payload["HtmlBody"] = html_body
    if reply_to:
        payload["ReplyTo"] = reply_to

    try:
        response = requests.post(
            api_url,
            json=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": token,
            },
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise EmailDeliveryError(str(exc)) from exc

    if response.status_code >= 400:
        raise EmailDeliveryError(f"Postmark returned {response.status_code}: {response.text[:300]}")


def send_email(config, subject: str, recipients, body: str, reply_to: str = None, html_body: str = None):
    if isinstance(recipients, str):
        recipients = [recipients]
    recipients = [item for item in recipients if item]
    if not recipients:
        raise EmailDeliveryError("No email recipients configured")

    return _send_postmark(config, subject, recipients, body, reply_to=reply_to, html_body=html_body)
