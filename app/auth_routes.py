import html
import secrets
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for

from app import limiter
from app.auth_helpers import (
    account_database_configured,
    clear_account_session,
    get_account_store,
    parse_admin_emails,
    set_account_session,
)
from app.utils.account_store import normalize_email, normalize_multiline_text, normalize_text
from app.utils.email_sender import EmailDeliveryError, send_email
from app.utils.ror_client import search_ror_organizations


auth = Blueprint("auth", __name__, url_prefix="/auth")


def _safe_next_url(value: str) -> str:
    if not value:
        return url_for("home.index")
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return url_for("home.index")
    return value if value.startswith("/") else url_for("home.index")


def _admin_recipients():
    recipients = list(parse_admin_emails(current_app.config.get("AUTH_ADMIN_EMAILS")))
    contact_email = current_app.config.get("CONTACT_EMAIL")
    if not recipients and contact_email:
        recipients.append(contact_email)
    return recipients


LOGIN_NONCE_SESSION_KEY = "login_nonce"


def _login_nonce() -> str:
    """Identifies this browser so the emailed link can be bound to it.

    Kept out of ACCOUNT_SESSION_KEYS on purpose: it must survive the session
    reset that set_account_session performs on a successful login.
    """
    nonce = session.get(LOGIN_NONCE_SESSION_KEY)
    if not nonce:
        nonce = secrets.token_urlsafe(16)
        session[LOGIN_NONCE_SESSION_KEY] = nonce
        session.permanent = True
    return nonce


def _token_lifetime_label() -> str:
    seconds = int(current_app.config.get("AUTH_TOKEN_MAX_AGE_SECONDS", 1800))
    if seconds >= 7200:
        hours = round(seconds / 3600)
        return f"{hours} hours"
    minutes = max(1, round(seconds / 60))
    return f"{minutes} minutes"


def _send_login_link(email: str, token: str, next_url: str) -> str:
    verify_url = url_for("auth.verify", token=token, next=next_url, _external=True)
    subject = "Your Regulated Plants login link"
    lifetime = _token_lifetime_label()
    body = f"""
Use this link to sign in to the Regulated Plants Database:

{verify_url}

This link expires in {lifetime} and can be used once. If you did not request it, you can ignore this email.
""".strip()

    # A real anchor stops corporate link-rewriters having to re-detect the URL in
    # plain text, which is where they truncate long tokens.
    safe_url = html.escape(verify_url, quote=True)
    html_body = f"""
<html><body style="font-family:Helvetica,Arial,sans-serif;font-size:15px;color:#15234A;">
<p>Use this link to sign in to the Regulated Plants Database:</p>
<p><a href="{safe_url}" style="color:#15234A;font-weight:600;">Sign in to Regulated Plants</a></p>
<p style="font-size:13px;color:#6c757d;">If the button does not work, copy this address into your browser:<br>
<span style="word-break:break-all;">{safe_url}</span></p>
<p style="font-size:13px;color:#6c757d;">This link expires in {lifetime} and can be used once.
If you did not request it, you can ignore this email.</p>
</body></html>
""".strip()

    if current_app.config.get("AUTH_DEV_SHOW_MAGIC_LINK"):
        return verify_url

    send_email(current_app.config, subject, email, body, html_body=html_body)
    return verify_url


def _send_access_request_notice(account: dict):
    recipients = _admin_recipients()
    if not recipients:
        current_app.logger.info("No admin recipients configured for access request notices")
        return

    admin_url = url_for("admin.accounts", status="pending", _external=True)
    subject = "Regulated Plants access request"
    body = f"""
A new access request is pending review.

Name: {account["full_name"]}
Email: {account["email"]}
Organization: {account["organization_name"]}

Reason:
{account["purpose"]}

Review pending accounts:
{admin_url}
""".strip()
    send_email(current_app.config, subject, recipients, body, reply_to=account["email"])


def _database_required_response(template_name: str, **context):
    if account_database_configured():
        return None
    flash("Account access is not configured yet. Set APP_DATABASE_URL before accepting logins.", "error")
    return render_template(template_name, **context), 503


@auth.route("/signup", methods=["GET", "POST"])
@limiter.limit("6 per hour", methods=["POST"])
def signup():
    next_url = _safe_next_url(request.values.get("next"))
    initial_email = normalize_email(request.values.get("email"))
    default_context = {
        "email": initial_email,
        "full_name": "",
        "organization_name": "",
        "purpose": "",
        "next_url": next_url,
    }

    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        full_name = normalize_text(request.form.get("full_name"), 160)
        organization_name = normalize_text(request.form.get("organization_name"), 200)
        purpose = normalize_multiline_text(request.form.get("purpose"), 2000)
        context = {
            "email": email,
            "full_name": full_name,
            "organization_name": organization_name,
            "purpose": purpose,
            "next_url": next_url,
        }

        config_response = _database_required_response("auth/signup.html", **context)
        if config_response:
            return config_response

        if not email:
            flash("Enter a valid email address.", "error")
            return render_template("auth/signup.html", **context), 400
        if not full_name:
            flash("Enter your name.", "error")
            return render_template("auth/signup.html", **context), 400
        if not organization_name:
            flash("Enter your organization.", "error")
            return render_template("auth/signup.html", **context), 400
        if not purpose:
            flash("Tell us why you want access.", "error")
            return render_template("auth/signup.html", **context), 400

        try:
            account, result = get_account_store().request_account(email, full_name, organization_name, purpose)
        except Exception as exc:
            current_app.logger.error("Unable to create access request: %s", exc)
            flash("We could not save your access request. Please try again later.", "error")
            return render_template("auth/signup.html", **context), 500

        if result == "active":
            flash("Your account is already approved. Sign in to continue.", "success")
            return redirect(url_for("auth.login", next=next_url, email=email))
        if result == "revoked":
            flash("This account is not eligible for self-service access. Contact the project team.", "error")
            return render_template("auth/signup.html", **context), 403

        try:
            _send_access_request_notice(account)
        except EmailDeliveryError as exc:
            current_app.logger.warning("Unable to send access request notice: %s", exc)

        return render_template("auth/signup_received.html", email=email)

    config_response = _database_required_response("auth/signup.html", **default_context)
    if config_response:
        return config_response
    return render_template("auth/signup.html", **default_context)


@auth.route("/login", methods=["GET", "POST"])
@limiter.limit("8 per hour", methods=["POST"])
def login():
    next_url = _safe_next_url(request.values.get("next"))
    email = normalize_email(request.values.get("email"))

    if request.method == "POST":
        context = {"email": email, "next_url": next_url}
        config_response = _database_required_response("auth/login.html", **context)
        if config_response:
            return config_response

        if not email:
            flash("Enter a valid email address.", "error")
            return render_template("auth/login.html", **context), 400

        try:
            account = get_account_store().get_account_by_email(email)
        except Exception as exc:
            current_app.logger.error("Unable to load account for login: %s", exc)
            flash("We could not check your account. Please try again later.", "error")
            return render_template("auth/login.html", **context), 500

        if not account:
            flash("Request access before signing in.", "error")
            return redirect(url_for("auth.signup", email=email, next=next_url))
        if account["status"] == "pending":
            return render_template("auth/signup_received.html", email=email, pending=True), 403
        if account["status"] == "rejected":
            flash("This access request was not approved. You may submit a new request if your use case has changed.", "error")
            return redirect(url_for("auth.signup", email=email, next=next_url))
        if account["status"] == "revoked":
            flash("This account no longer has access. Contact the project team.", "error")
            return render_template("auth/login.html", **context), 403

        try:
            token = get_account_store().create_login_token(account["id"], browser_nonce=_login_nonce())
            dev_link = _send_login_link(email, token, next_url)
        except Exception as exc:
            current_app.logger.error("Unable to send account login email: %s", exc)
            flash("We could not send the login email. Please try again later.", "error")
            return render_template("auth/login.html", **context), 500

        return render_template(
            "auth/login_sent.html",
            email=email,
            lifetime=_token_lifetime_label(),
            dev_link=dev_link if current_app.config.get("AUTH_DEV_SHOW_MAGIC_LINK") else None,
        )

    context = {"email": email, "next_url": next_url}
    config_response = _database_required_response("auth/login.html", **context)
    if config_response:
        return config_response
    return render_template("auth/login.html", **context)


@auth.route("/api/affiliations")
@limiter.limit("120 per hour")
def affiliations():
    if not current_app.config.get("AUTH_ROR_ENABLED"):
        return jsonify({"results": []})

    query = request.args.get("q", "").strip()
    if len(query) < 3:
        return jsonify({"results": []})

    try:
        results = search_ror_organizations(
            query,
            current_app.config.get("ROR_API_BASE_URL", "https://api.ror.org/v2/organizations"),
            current_app.config.get("ROR_API_TIMEOUT_SECONDS", 4),
            limit=10,
        )
    except Exception as exc:
        current_app.logger.warning("Unable to search ROR affiliations for %r: %s", query, exc)
        return jsonify({"results": []})

    return jsonify({"results": results})


def _login_token_error_redirect(status: str, next_url: str):
    if status == "expired":
        flash("That login link has expired. Please request a new link.", "error")
        return redirect(url_for("auth.login", next=next_url))
    if status in {"invalid", "used"}:
        flash("That login link is invalid or has already been used. Please request a new link.", "error")
        return redirect(url_for("auth.login", next=next_url))
    if status == "wrong_browser":
        flash("Confirm the email address this link was sent to in order to continue.", "error")
        return redirect(url_for("auth.login", next=next_url))
    if status == "pending":
        flash("Your access request is still pending review.", "error")
        return redirect(url_for("auth.login", next=next_url))
    if status == "rejected":
        flash("This access request was not approved.", "error")
        return redirect(url_for("auth.signup", next=next_url))
    if status == "revoked":
        flash("This account no longer has access.", "error")
        return redirect(url_for("auth.login", next=next_url))

    flash("That login link could not be verified. Please request a new link.", "error")
    return redirect(url_for("auth.login", next=next_url))


@auth.route("/verify", methods=["GET", "POST"])
def verify():
    token = request.args.get("token", "")
    if request.method == "POST":
        token = request.form.get("token", "")
    next_url = _safe_next_url(request.args.get("next"))
    if request.method == "POST":
        next_url = _safe_next_url(request.form.get("next"))

    if not account_database_configured():
        flash("Account access is not configured yet. Set APP_DATABASE_URL before accepting logins.", "error")
        return redirect(url_for("auth.login", next=next_url))

    if request.method == "GET":
        try:
            account, status, same_browser = get_account_store().peek_login_token(
                token, browser_nonce=session.get(LOGIN_NONCE_SESSION_KEY)
            )
        except Exception as exc:
            current_app.logger.error("Unable to inspect login token: %s", exc)
            flash("That login link could not be verified. Please request a new link.", "error")
            return redirect(url_for("auth.login", next=next_url))

        if status != "active" or not account:
            return _login_token_error_redirect(status, next_url)

        return render_template(
            "auth/verify.html",
            token=token,
            next_url=next_url,
            # Withholding the address is the point of the challenge: the visitor
            # has to already know it.
            email=account["email"] if same_browser else None,
            confirm_email_required=not same_browser,
        )

    try:
        account, status = get_account_store().consume_login_token(
            token,
            browser_nonce=session.get(LOGIN_NONCE_SESSION_KEY),
            verified_email=request.form.get("confirm_email"),
        )
    except Exception as exc:
        current_app.logger.error("Unable to verify login token: %s", exc)
        flash("That login link could not be verified. Please request a new link.", "error")
        return redirect(url_for("auth.login", next=next_url))

    if status == "wrong_browser":
        # Keep the token alive and let them retry rather than sending them back
        # to request a fresh link.
        flash("That email address did not match. Enter the address this link was sent to.", "error")
        return render_template(
            "auth/verify.html",
            token=token,
            next_url=next_url,
            email=None,
            confirm_email_required=True,
        ), 400
    if status != "active":
        return _login_token_error_redirect(status, next_url)
    if not account:
        flash("That login link could not be verified. Please request a new link.", "error")
        return redirect(url_for("auth.login", next=next_url))

    set_account_session(account)
    session.pop(LOGIN_NONCE_SESSION_KEY, None)
    flash("You are signed in.", "success")
    return redirect(next_url)


@auth.route("/logout", methods=["POST"])
def logout():
    clear_account_session()
    flash("You are signed out.", "success")
    return redirect(url_for("home.index"))
