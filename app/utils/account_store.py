import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr


ACCOUNT_STATUSES = ("pending", "active", "rejected", "revoked")
ACCOUNT_ROLES = ("user", "admin")


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def normalize_email(value: str) -> str:
    _, parsed = parseaddr(value or "")
    return parsed.strip().lower()


def email_domain(email: str) -> str:
    normalized = normalize_email(email)
    if "@" not in normalized:
        return ""
    return normalized.rsplit("@", 1)[1].strip().lower()


def normalize_text(value: str, limit: int = None) -> str:
    normalized = " ".join(str(value or "").strip().split())
    if limit is not None:
        return normalized[:limit]
    return normalized


def normalize_multiline_text(value: str, limit: int = None) -> str:
    normalized = str(value or "").strip()
    normalized = "\n".join(" ".join(line.split()) for line in normalized.splitlines())
    normalized = "\n".join(line for line in normalized.splitlines() if line)
    if limit is not None:
        return normalized[:limit]
    return normalized


def hash_token(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


class AccountStore:
    def __init__(self, database_url: str, login_token_ttl_seconds: int = 1800):
        self.database_url = (database_url or "").strip()
        self.login_token_ttl_seconds = max(60, int(login_token_ttl_seconds or 1800))
        if not self.database_url:
            raise ValueError("APP_DATABASE_URL is required for account storage")
        self.ensure_schema()

    def _connect(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("Install psycopg to use Postgres account storage") from exc

        return psycopg.connect(self.database_url, row_factory=dict_row)

    def ensure_schema(self):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS accounts (
                        id UUID PRIMARY KEY,
                        email TEXT UNIQUE NOT NULL,
                        full_name TEXT NOT NULL,
                        organization_name TEXT NOT NULL,
                        purpose TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        role TEXT NOT NULL DEFAULT 'user',
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL,
                        approved_at TIMESTAMPTZ,
                        rejected_at TIMESTAMPTZ,
                        revoked_at TIMESTAMPTZ,
                        reviewed_by UUID REFERENCES accounts(id),
                        review_note TEXT,
                        last_login_at TIMESTAMPTZ,
                        session_version INTEGER NOT NULL DEFAULT 1,
                        CONSTRAINT accounts_status_check
                            CHECK (status IN ('pending', 'active', 'rejected', 'revoked')),
                        CONSTRAINT accounts_role_check
                            CHECK (role IN ('user', 'admin'))
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS login_tokens (
                        id UUID PRIMARY KEY,
                        account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                        token_hash TEXT UNIQUE NOT NULL,
                        expires_at TIMESTAMPTZ NOT NULL,
                        used_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cur.execute(
                    "ALTER TABLE login_tokens ADD COLUMN IF NOT EXISTS browser_nonce_hash TEXT"
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS admin_audit_events (
                        id UUID PRIMARY KEY,
                        admin_account_id UUID REFERENCES accounts(id),
                        target_account_id UUID REFERENCES accounts(id),
                        action TEXT NOT NULL,
                        note TEXT,
                        created_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_accounts_status_created ON accounts(status, created_at DESC)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_login_tokens_account ON login_tokens(account_id)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_login_tokens_expires ON login_tokens(expires_at)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_admin_audit_target ON admin_audit_events(target_account_id, created_at DESC)"
                )
            conn.commit()

    def ensure_admin_accounts(self, admin_emails):
        emails = [normalize_email(email) for email in admin_emails if normalize_email(email)]
        if not emails:
            return

        now = utc_now()
        with self._connect() as conn:
            with conn.cursor() as cur:
                for email in emails:
                    cur.execute("SELECT id FROM accounts WHERE email = %s", (email,))
                    existing = cur.fetchone()
                    if existing:
                        cur.execute(
                            """
                            UPDATE accounts
                            SET role = 'admin',
                                status = 'active',
                                approved_at = COALESCE(approved_at, %s),
                                updated_at = %s
                            WHERE email = %s
                            """,
                            (now, now, email),
                        )
                        continue

                    cur.execute(
                        """
                        INSERT INTO accounts (
                            id, email, full_name, organization_name, purpose,
                            status, role, created_at, updated_at, approved_at
                        )
                        VALUES (%s, %s, %s, %s, %s, 'active', 'admin', %s, %s, %s)
                        """,
                        (
                            str(uuid.uuid4()),
                            email,
                            email,
                            "Regulated Plants Database",
                            "Administrator configured by AUTH_ADMIN_EMAILS.",
                            now,
                            now,
                            now,
                        ),
                    )
            conn.commit()

    def request_account(self, email: str, full_name: str, organization_name: str, purpose: str):
        normalized_email = normalize_email(email)
        name = normalize_text(full_name, 160)
        organization = normalize_text(organization_name, 200)
        access_purpose = normalize_multiline_text(purpose, 2000)
        now = utc_now()

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM accounts WHERE email = %s", (normalized_email,))
                existing = cur.fetchone()
                if existing and existing["status"] == "active":
                    return existing, "active"
                if existing and existing["status"] == "revoked":
                    return existing, "revoked"

                if existing:
                    cur.execute(
                        """
                        UPDATE accounts
                        SET full_name = %s,
                            organization_name = %s,
                            purpose = %s,
                            status = 'pending',
                            updated_at = %s,
                            rejected_at = NULL,
                            review_note = NULL
                        WHERE id = %s
                        RETURNING *
                        """,
                        (name, organization, access_purpose, now, existing["id"]),
                    )
                    account = cur.fetchone()
                    conn.commit()
                    return account, "updated"

                cur.execute(
                    """
                    INSERT INTO accounts (
                        id, email, full_name, organization_name, purpose,
                        status, role, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, 'pending', 'user', %s, %s)
                    RETURNING *
                    """,
                    (
                        str(uuid.uuid4()),
                        normalized_email,
                        name,
                        organization,
                        access_purpose,
                        now,
                        now,
                    ),
                )
                account = cur.fetchone()
            conn.commit()
        return account, "created"

    def get_account_by_email(self, email: str):
        normalized_email = normalize_email(email)
        if not normalized_email:
            return None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM accounts WHERE email = %s", (normalized_email,))
                return cur.fetchone()

    def get_account_by_id(self, account_id: str):
        if not account_id:
            return None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM accounts WHERE id = %s", (account_id,))
                return cur.fetchone()

    def get_active_account_for_session(self, account_id: str, session_version: int):
        if not account_id:
            return None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM accounts
                    WHERE id = %s
                      AND status = 'active'
                      AND session_version = %s
                    """,
                    (account_id, int(session_version or 0)),
                )
                return cur.fetchone()

    @staticmethod
    def _browser_nonce_matches(row, browser_nonce) -> bool:
        """A token is bound to the browser that requested it.

        Tokens issued before binding existed carry no hash and stay unbound, so
        links already sitting in inboxes keep working after this ships.
        """
        expected = row.get("browser_nonce_hash")
        if not expected:
            return True
        return bool(browser_nonce) and hash_token(browser_nonce) == expected

    def create_login_token(self, account_id: str, browser_nonce: str = None) -> str:
        raw_token = secrets.token_urlsafe(32)
        token_id = str(uuid.uuid4())
        now = utc_now()
        expires_at = now + timedelta(seconds=self.login_token_ttl_seconds)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO login_tokens (id, account_id, token_hash, expires_at, created_at, browser_nonce_hash)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        token_id,
                        account_id,
                        hash_token(raw_token),
                        expires_at,
                        now,
                        hash_token(browser_nonce) if browser_nonce else None,
                    ),
                )
            conn.commit()
        return raw_token

    def peek_login_token(self, raw_token: str, browser_nonce: str = None):
        """Returns (row, status, same_browser).

        same_browser is False when the link is being opened somewhere other than
        the browser that asked for it, which the caller must then challenge.
        """
        token_digest = hash_token(raw_token)
        now = utc_now()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        login_tokens.id AS token_id,
                        login_tokens.expires_at,
                        login_tokens.used_at,
                        login_tokens.browser_nonce_hash,
                        accounts.*
                    FROM login_tokens
                    JOIN accounts ON accounts.id = login_tokens.account_id
                    WHERE login_tokens.token_hash = %s
                    """,
                    (token_digest,),
                )
                row = cur.fetchone()

        if not row:
            return None, "invalid", False
        if row["used_at"]:
            return None, "used", False
        if row["expires_at"] < now:
            return None, "expired", False
        if row["status"] != "active":
            return row, row["status"], False
        return row, "active", self._browser_nonce_matches(row, browser_nonce)

    def consume_login_token(self, raw_token: str, browser_nonce: str = None, verified_email: str = None):
        token_digest = hash_token(raw_token)
        now = utc_now()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        login_tokens.id AS token_id,
                        login_tokens.expires_at,
                        login_tokens.used_at,
                        login_tokens.browser_nonce_hash,
                        accounts.*
                    FROM login_tokens
                    JOIN accounts ON accounts.id = login_tokens.account_id
                    WHERE login_tokens.token_hash = %s
                    FOR UPDATE
                    """,
                    (token_digest,),
                )
                row = cur.fetchone()
                if not row:
                    conn.commit()
                    return None, "invalid"
                if row["used_at"]:
                    conn.commit()
                    return None, "used"
                if row["expires_at"] < now:
                    conn.commit()
                    return None, "expired"
                if row["status"] != "active":
                    conn.commit()
                    return row, row["status"]
                if not self._browser_nonce_matches(row, browser_nonce):
                    if normalize_email(verified_email) != row["email"]:
                        # Deliberately leaves used_at NULL: a scanner probing the
                        # form must not burn the token the real recipient needs.
                        conn.commit()
                        return None, "wrong_browser"

                cur.execute("UPDATE login_tokens SET used_at = %s WHERE id = %s", (now, row["token_id"]))
                cur.execute("UPDATE accounts SET last_login_at = %s, updated_at = %s WHERE id = %s", (now, now, row["id"]))
            conn.commit()

        account = self.get_account_by_id(row["id"])
        return account, "active"

    def list_accounts(self, status: str = None):
        with self._connect() as conn:
            with conn.cursor() as cur:
                if status in ACCOUNT_STATUSES:
                    cur.execute(
                        """
                        SELECT *
                        FROM accounts
                        WHERE status = %s
                        ORDER BY created_at DESC
                        """,
                        (status,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT *
                        FROM accounts
                        ORDER BY
                            CASE status
                                WHEN 'pending' THEN 1
                                WHEN 'active' THEN 2
                                WHEN 'rejected' THEN 3
                                WHEN 'revoked' THEN 4
                                ELSE 5
                            END,
                            created_at DESC
                        """
                    )
                return cur.fetchall()

    def set_account_status(self, target_account_id: str, status: str, admin_account_id: str = None, note: str = ""):
        if status not in ACCOUNT_STATUSES:
            raise ValueError(f"Unsupported account status: {status}")

        note = normalize_multiline_text(note, 2000)
        now = utc_now()

        with self._connect() as conn:
            with conn.cursor() as cur:
                if status == "active":
                    cur.execute(
                        """
                        UPDATE accounts
                        SET status = 'active',
                            updated_at = %s,
                            approved_at = %s,
                            rejected_at = NULL,
                            revoked_at = NULL,
                            reviewed_by = %s,
                            review_note = %s
                        WHERE id = %s
                        RETURNING *
                        """,
                        (now, now, admin_account_id, note or None, target_account_id),
                    )
                elif status == "rejected":
                    cur.execute(
                        """
                        UPDATE accounts
                        SET status = 'rejected',
                            updated_at = %s,
                            approved_at = NULL,
                            rejected_at = %s,
                            revoked_at = NULL,
                            reviewed_by = %s,
                            review_note = %s,
                            session_version = session_version + 1
                        WHERE id = %s
                        RETURNING *
                        """,
                        (now, now, admin_account_id, note or None, target_account_id),
                    )
                elif status == "revoked":
                    cur.execute(
                        """
                        UPDATE accounts
                        SET status = 'revoked',
                            updated_at = %s,
                            revoked_at = %s,
                            reviewed_by = %s,
                            review_note = %s,
                            session_version = session_version + 1
                        WHERE id = %s
                        RETURNING *
                        """,
                        (now, now, admin_account_id, note or None, target_account_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE accounts
                        SET status = 'pending',
                            updated_at = %s,
                            reviewed_by = %s,
                            review_note = %s
                        WHERE id = %s
                        RETURNING *
                        """,
                        (now, admin_account_id, note or None, target_account_id),
                    )
                account = cur.fetchone()
                if account:
                    cur.execute(
                        """
                        INSERT INTO admin_audit_events (
                            id, admin_account_id, target_account_id, action, note, created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(uuid.uuid4()),
                            admin_account_id,
                            target_account_id,
                            status,
                            note or None,
                            now,
                        ),
                    )
            conn.commit()
        return account
