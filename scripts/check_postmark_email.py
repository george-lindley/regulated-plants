import argparse
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.utils.email_sender import send_email


def main():
    parser = argparse.ArgumentParser(description="Check configured Postmark email delivery.")
    parser.add_argument("--to", help="Recipient for a real test email. Defaults to MAIL_DEFAULT_SENDER.")
    args = parser.parse_args()

    app = create_app()
    config = app.config

    recipient = args.to or config.get("MAIL_DEFAULT_SENDER")
    if not recipient:
        print("No recipient configured. Pass --to or set MAIL_DEFAULT_SENDER.", file=sys.stderr)
        return 2

    try:
        send_email(
            config,
            "Regulated Plants email delivery test",
            recipient,
            "This is a test email from the Regulated Plants Postmark configuration.",
        )
    except Exception as exc:
        print(f"Postmark email check failed: {exc}", file=sys.stderr)
        return 1

    print(f"Postmark email delivery succeeded to {recipient}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
