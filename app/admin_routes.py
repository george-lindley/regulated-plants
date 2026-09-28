from functools import wraps

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from app.auth_helpers import account_logged_in, current_account, current_user_is_admin, get_account_store
from app.utils.account_store import ACCOUNT_STATUSES
from app.utils.email_sender import EmailDeliveryError, send_email


admin = Blueprint("admin", __name__, url_prefix="/admin")


def _current_path() -> str:
    return request.full_path if request.query_string else request.path


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not account_logged_in():
            return redirect(url_for("auth.login", next=_current_path()))
        if not current_user_is_admin():
            abort(403)
        return view_func(*args, **kwargs)

    return wrapped


@admin.route("")
@admin_required
def index():
    return redirect(url_for("admin.accounts", status="pending"))


@admin.route("/accounts")
@admin_required
def accounts():
    selected_status = request.args.get("status", "pending")
    if selected_status not in ACCOUNT_STATUSES and selected_status != "all":
        selected_status = "pending"

    store = get_account_store()
    all_accounts = store.list_accounts()
    if selected_status == "all":
        visible_accounts = all_accounts
    else:
        visible_accounts = [account for account in all_accounts if account["status"] == selected_status]

    counts = {status: 0 for status in ACCOUNT_STATUSES}
    for account in all_accounts:
        counts[account["status"]] = counts.get(account["status"], 0) + 1

    return render_template(
        "admin/accounts.html",
        accounts=visible_accounts,
        counts=counts,
        selected_status=selected_status,
        statuses=ACCOUNT_STATUSES,
    )


def _send_account_status_email(account: dict, status: str):
    login_url = url_for("auth.login", _external=True)
    subject_by_status = {
        "active": "Your Regulated Plants account is approved",
        "rejected": "Your Regulated Plants access request was reviewed",
        "revoked": "Your Regulated Plants account access changed",
    }

    if status == "active":
        body = f"""
Your Regulated Plants Database account has been approved.

You can now sign in with your email address:
{login_url}
""".strip()
    elif status == "rejected":
        body = """
Your Regulated Plants Database access request was reviewed and was not approved at this time.

If your use case changes, you may submit a new access request.
""".strip()
    elif status == "revoked":
        body = """
Your Regulated Plants Database account access has been revoked.

If you believe this was a mistake, contact the project team.
""".strip()
    else:
        return

    send_email(
        current_app.config,
        subject_by_status[status],
        account["email"],
        body,
    )


@admin.route("/accounts/<account_id>/<action>", methods=["POST"])
@admin_required
def update_account(account_id: str, action: str):
    action_to_status = {
        "approve": "active",
        "reject": "rejected",
        "revoke": "revoked",
    }
    status = action_to_status.get(action)
    if not status:
        abort(404)

    admin_account = current_account()
    if str(admin_account["id"]) == str(account_id) and status in {"rejected", "revoked"}:
        flash("You cannot reject or revoke your own admin account.", "error")
        return redirect(url_for("admin.accounts", status="active"))

    account = get_account_store().set_account_status(
        target_account_id=account_id,
        status=status,
        admin_account_id=admin_account["id"],
        note=request.form.get("note"),
    )
    if not account:
        abort(404)

    try:
        _send_account_status_email(account, status)
        flash(f"{account['email']} is now {status}. Notification sent.", "success")
    except EmailDeliveryError as exc:
        current_app.logger.warning("Unable to send account status email to %s: %s", account["email"], exc)
        flash(f"{account['email']} is now {status}, but the notification email could not be sent.", "error")

    return redirect(url_for("admin.accounts", status=account["status"]))
