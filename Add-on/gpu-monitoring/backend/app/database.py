import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .auth import hash_password
from .config import Settings


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self, settings: Settings) -> None:
        if self.path != ":memory:":
            Path(self.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    nickname TEXT,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'USER' CHECK(role IN ('USER','MANAGER','ADMIN','SUPER_ADMIN')),
                    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','INACTIVE','SUSPENDED','DELETED')),
                    created_at TEXT NOT NULL,
                    last_login_at TEXT,
                    last_active_at TEXT,
                    deleted_at TEXT
                );
                CREATE TABLE IF NOT EXISTS admin_activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER,
                    admin_name TEXT,
                    action TEXT NOT NULL,
                    target_type TEXT,
                    target_id TEXT,
                    previous_value TEXT,
                    new_value TEXT,
                    description TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(admin_id) REFERENCES users(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_logs_created_at ON admin_activity_logs(created_at DESC);
                """
            )
            exists = connection.execute("SELECT id FROM users WHERE email = ?", (settings.initial_admin_email,)).fetchone()
            if not exists:
                connection.execute(
                    "INSERT INTO users(name,nickname,email,password_hash,role,status,created_at) VALUES(?,?,?,?,?,?,?)",
                    (settings.initial_admin_name, "admin", settings.initial_admin_email, hash_password(settings.initial_admin_password), "SUPER_ADMIN", "ACTIVE", utc_now()),
                )

    def user_by_email(self, email: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM users WHERE email = ? AND deleted_at IS NULL", (email,)).fetchone()

    def user_by_id(self, user_id: int) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM users WHERE id = ? AND deleted_at IS NULL", (user_id,)).fetchone()

    def update_login(self, user_id: int) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute("UPDATE users SET last_login_at = ?, last_active_at = ? WHERE id = ?", (now, now, user_id))

    def add_log(self, *, admin: sqlite3.Row | None, action: str, request: Any, target_type: str | None = None, target_id: str | None = None, description: str | None = None, previous_value: Any = None, new_value: Any = None) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO admin_activity_logs(admin_id,admin_name,action,target_type,target_id,previous_value,new_value,description,ip_address,user_agent,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    admin["id"] if admin else None, admin["name"] if admin else None, action, target_type, target_id,
                    json.dumps(previous_value, ensure_ascii=False) if previous_value is not None else None,
                    json.dumps(new_value, ensure_ascii=False) if new_value is not None else None,
                    description, request.client.host if request.client else None, request.headers.get("user-agent"), utc_now(),
                ),
            )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
