from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from backend.app.schemas.research import (
    AgentStep,
    ClaimScore,
    ConfidenceBreakdown,
    ResearchMessage,
    ResearchReport,
    ReportSection,
    SessionSummary,
    SourceItem,
    UserProfile,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


class ResearchStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._initialize()

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS auth_tokens (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS research_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    depth TEXT NOT NULL,
                    pinned INTEGER NOT NULL DEFAULT 0,
                    bookmarked INTEGER NOT NULL DEFAULT 0,
                    compare_selected INTEGER NOT NULL DEFAULT 0,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    latest_query TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS research_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES research_sessions(session_id)
                );
                CREATE TABLE IF NOT EXISTS research_reports (
                    report_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES research_sessions(session_id)
                );
                CREATE TABLE IF NOT EXISTS research_steps (
                    step_id TEXT PRIMARY KEY,
                    report_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(report_id) REFERENCES research_reports(report_id)
                );
                CREATE TABLE IF NOT EXISTS research_feedback (
                    feedback_id TEXT PRIMARY KEY,
                    report_id TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(report_id) REFERENCES research_reports(report_id)
                );
                """
            )

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        encoded = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
        return encoded.hex()

    def create_user(self, email: str, password: str, display_name: str) -> UserProfile:
        created_at = utcnow().isoformat()
        salt = secrets.token_hex(8)
        password_hash = f"{salt}${self._hash_password(password, salt)}"
        with self.connection() as conn:
            cursor = conn.execute(
                "INSERT INTO users(email, display_name, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (email.lower(), display_name, password_hash, created_at),
            )
            user_id = int(cursor.lastrowid)
        return UserProfile(user_id=user_id, email=email.lower(), display_name=display_name, created_at=datetime.fromisoformat(created_at))

    def authenticate(self, email: str, password: str) -> UserProfile | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
        if row is None:
            return None
        salt, expected_hash = row["password_hash"].split("$", 1)
        if self._hash_password(password, salt) != expected_hash:
            return None
        return UserProfile(
            user_id=int(row["id"]),
            email=row["email"],
            display_name=row["display_name"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def issue_token(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO auth_tokens(token, user_id, created_at) VALUES (?, ?, ?)",
                (token, user_id, utcnow().isoformat()),
            )
        return token

    def revoke_token(self, token: str) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))

    def user_for_token(self, token: str) -> UserProfile | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT users.* FROM auth_tokens
                JOIN users ON users.id = auth_tokens.user_id
                WHERE auth_tokens.token = ?
                """,
                (token,),
            ).fetchone()
        if row is None:
            return None
        return UserProfile(
            user_id=int(row["id"]),
            email=row["email"],
            display_name=row["display_name"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def create_session(self, user_id: int, title: str, mode: str, depth: str, tags: list[str]) -> SessionSummary:
        session_id = str(uuid.uuid4())
        now = utcnow().isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO research_sessions(
                    session_id, user_id, title, mode, depth, tags_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, user_id, title, mode, depth, json.dumps(tags), now, now),
            )
        return self.get_session(user_id, session_id)

    def update_session(self, user_id: int, session_id: str, fields: dict) -> SessionSummary:
        updates = []
        params: list[object] = []
        if "title" in fields and fields["title"] is not None:
            updates.append("title = ?")
            params.append(fields["title"])
        if "pinned" in fields and fields["pinned"] is not None:
            updates.append("pinned = ?")
            params.append(1 if fields["pinned"] else 0)
        if "bookmarked" in fields and fields["bookmarked"] is not None:
            updates.append("bookmarked = ?")
            params.append(1 if fields["bookmarked"] else 0)
        if "compare_selected" in fields and fields["compare_selected"] is not None:
            updates.append("compare_selected = ?")
            params.append(1 if fields["compare_selected"] else 0)
        if "tags" in fields and fields["tags"] is not None:
            updates.append("tags_json = ?")
            params.append(json.dumps(fields["tags"]))
        updates.append("updated_at = ?")
        params.append(utcnow().isoformat())
        params.extend([session_id, user_id])
        with self.connection() as conn:
            conn.execute(
                f"UPDATE research_sessions SET {', '.join(updates)} WHERE session_id = ? AND user_id = ?",
                params,
            )
        return self.get_session(user_id, session_id)

    def list_sessions(self, user_id: int) -> list[SessionSummary]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM research_sessions WHERE user_id = ? ORDER BY pinned DESC, updated_at DESC",
                (user_id,),
            ).fetchall()
        return [self._session_from_row(row) for row in rows]

    def get_session(self, user_id: int, session_id: str) -> SessionSummary:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM research_sessions WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            ).fetchone()
        if row is None:
            raise KeyError(session_id)
        return self._session_from_row(row)

    def delete_session(self, user_id: int, session_id: str) -> None:
        with self.connection() as conn:
            report_rows = conn.execute(
                "SELECT report_id FROM research_reports WHERE session_id = ?",
                (session_id,),
            ).fetchall()
            for row in report_rows:
                conn.execute("DELETE FROM research_steps WHERE report_id = ?", (row["report_id"],))
                conn.execute("DELETE FROM research_feedback WHERE report_id = ?", (row["report_id"],))
            conn.execute("DELETE FROM research_reports WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM research_messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM research_sessions WHERE session_id = ? AND user_id = ?", (session_id, user_id))

    def add_message(self, session_id: str, role: str, content: str) -> ResearchMessage:
        message = ResearchMessage(
            message_id=str(uuid.uuid4()),
            role=role,  # type: ignore[arg-type]
            content=content,
            created_at=utcnow(),
        )
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO research_messages(message_id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (message.message_id, session_id, role, content, message.created_at.isoformat()),
            )
            conn.execute(
                "UPDATE research_sessions SET latest_query = ?, updated_at = ? WHERE session_id = ?",
                (content if role == "user" else None, utcnow().isoformat(), session_id),
            )
        return message

    def store_report(self, session_id: str, report: ResearchReport, steps: list[AgentStep]) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO research_reports(report_id, session_id, payload_json, created_at) VALUES (?, ?, ?, ?)",
                (report.report_id, session_id, report.model_dump_json(), report.created_at.isoformat()),
            )
            for step in steps:
                conn.execute(
                    "INSERT INTO research_steps(step_id, report_id, payload_json, created_at) VALUES (?, ?, ?, ?)",
                    (step.step_id, report.report_id, step.model_dump_json(), utcnow().isoformat()),
                )
            conn.execute(
                "UPDATE research_sessions SET latest_query = ?, updated_at = ? WHERE session_id = ?",
                (report.query, utcnow().isoformat(), session_id),
            )

    def session_messages(self, session_id: str) -> list[ResearchMessage]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM research_messages WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
        return [
            ResearchMessage(
                message_id=row["message_id"],
                role=row["role"],
                content=row["content"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def session_reports(self, session_id: str) -> list[ResearchReport]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM research_reports WHERE session_id = ? ORDER BY created_at DESC",
                (session_id,),
            ).fetchall()
        return [ResearchReport.model_validate_json(row["payload_json"]) for row in rows]

    def session_steps(self, session_id: str) -> list[AgentStep]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT research_steps.payload_json
                FROM research_steps
                JOIN research_reports ON research_reports.report_id = research_steps.report_id
                WHERE research_reports.session_id = ?
                ORDER BY research_steps.created_at DESC
                """,
                (session_id,),
            ).fetchall()
        return [AgentStep.model_validate_json(row["payload_json"]) for row in rows]

    def record_feedback(self, report_id: str, target_type: str, target_key: str, value: str, notes: str | None) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO research_feedback(feedback_id, report_id, target_type, target_key, value, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), report_id, target_type, target_key, value, notes, utcnow().isoformat()),
            )

    def knowledge_graph(self, user_id: int) -> tuple[list[dict], list[dict]]:
        sessions = self.list_sessions(user_id)
        nodes: list[dict] = []
        edges: list[dict] = []
        for session in sessions:
            session_node = {"node_id": f"session:{session.session_id}", "label": session.title, "group": "session"}
            nodes.append(session_node)
            mode_id = f"mode:{session.mode}"
            if not any(node["node_id"] == mode_id for node in nodes):
                nodes.append({"node_id": mode_id, "label": session.mode.title(), "group": "mode"})
            edges.append({"source": session_node["node_id"], "target": mode_id, "weight": 1.0})
            for tag in session.tags:
                tag_id = f"tag:{tag}"
                if not any(node["node_id"] == tag_id for node in nodes):
                    nodes.append({"node_id": tag_id, "label": tag, "group": "tag"})
                edges.append({"source": session_node["node_id"], "target": tag_id, "weight": 1.0})
        return nodes, edges

    @staticmethod
    def _session_from_row(row: sqlite3.Row) -> SessionSummary:
        return SessionSummary(
            session_id=row["session_id"],
            title=row["title"],
            mode=row["mode"],
            depth=row["depth"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            pinned=bool(row["pinned"]),
            bookmarked=bool(row["bookmarked"]),
            compare_selected=bool(row["compare_selected"]),
            tags=json.loads(row["tags_json"]),
            latest_query=row["latest_query"],
        )
