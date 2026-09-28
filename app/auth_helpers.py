from flask import current_app, g, session

from app.utils.account_store import AccountStore, normalize_email


ACCOUNT_SESSION_KEYS = (
    "account_id",
    "account_email",
    "account_full_name",
    "account_role",
    "account_session_version",
    "account_logged_in_at",
    "researcher_email",
    "researcher_affiliation_name",
    "researcher_affiliation_ror_id",
    "researcher_logged_in_at",
)


def account_database_url() -> str:
    return (current_app.config.get("APP_DATABASE_URL") or "").strip()


def account_database_configured() -> bool:
    return bool(account_database_url())


def parse_admin_emails(value) -> tuple:
    if isinstance(value, (list, tuple, set)):
        raw_parts = value
    else:
        raw_parts = str(value or "").split(",")
    return tuple(normalize_email(part) for part in raw_parts if normalize_email(part))


def get_account_store() -> AccountStore:
    store = current_app.extensions.get("account_store")
    database_url = account_database_url()
    if not database_url:
        raise RuntimeError("APP_DATABASE_URL is not configured")
    if store is None:
        store = AccountStore(
            database_url=database_url,
            login_token_ttl_seconds=current_app.config.get("AUTH_TOKEN_MAX_AGE_SECONDS", 1800),
        )
        admin_emails = parse_admin_emails(current_app.config.get("AUTH_ADMIN_EMAILS"))
        store.ensure_admin_accounts(admin_emails)
        current_app.extensions["account_store"] = store
    return store


def clear_account_session():
    for key in ACCOUNT_SESSION_KEYS:
        session.pop(key, None)
    g.pop("current_account", None)


def set_account_session(account: dict):
    clear_account_session()
    session.permanent = True
    session["account_id"] = str(account["id"])
    session["account_email"] = account["email"]
    session["account_full_name"] = account["full_name"]
    session["account_role"] = account["role"]
    session["account_session_version"] = int(account["session_version"])
    session["account_logged_in_at"] = str(account.get("last_login_at") or "")
    g.current_account = account


def current_account():
    if hasattr(g, "current_account"):
        return g.current_account

    account_id = session.get("account_id")
    session_version = session.get("account_session_version")
    if not account_id or not session_version or not account_database_configured():
        g.current_account = None
        return None

    try:
        account = get_account_store().get_active_account_for_session(account_id, int(session_version))
    except Exception as exc:
        current_app.logger.warning("Unable to load account from session: %s", exc)
        g.current_account = None
        return None

    if not account:
        clear_account_session()
        g.current_account = None
        return None

    g.current_account = account
    return account


def account_logged_in() -> bool:
    return current_account() is not None


def current_user_is_admin() -> bool:
    account = current_account()
    return bool(account and account.get("role") == "admin")
