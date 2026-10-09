"""Private hosted-worker session persistence with immutable snapshots and CAS writes.

For multiple workers, implement the same store boundary over a managed transactional
store; do not put SQLite in ephemeral Cloud Run storage for durable rider sessions.
"""
from dataclasses import asdict
import json
import sqlite3

from controller_contracts import DiagnosticSession, Fact, Outcome, StepAttempt


class SessionConflict(RuntimeError):
    pass


def decode(raw):
    d = json.loads(raw)
    attempts = []
    for a in d.pop("attempted_steps"):
        a["outcome_enum"] = Outcome(a["outcome_enum"])
        a["applicability_symptoms"] = tuple(a.get("applicability_symptoms", []))
        a["observed_details"] = tuple((k, Fact(**v)) for k, v in a["observed_details"])
        attempts.append(StepAttempt(**a))
    d["current_symptoms"] = tuple(d["current_symptoms"])
    d["excluded_branches"] = tuple(d.get("excluded_branches", []))
    d["clarification_counts"] = tuple(tuple(x) for x in d["clarification_counts"])
    return DiagnosticSession(**d, attempted_steps=tuple(attempts))


class SQLiteSessionStore:
    def __init__(self, path):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT, version INTEGER, snapshot TEXT NOT NULL, PRIMARY KEY(id, version))")

    def load(self, session_id):
        row = self.db.execute("SELECT snapshot FROM sessions WHERE id=? ORDER BY version DESC LIMIT 1", (session_id,)).fetchone()
        if row is None:
            raise KeyError(session_id)
        return decode(row[0])

    def save(self, session, expected_version=None):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT MAX(version) FROM sessions WHERE id=?", (session.session_id,)).fetchone()
            current = row[0]
            if current != expected_version or (current is not None and session.version <= current):
                raise SessionConflict("Concurrent or stale session update")
            if current is not None:
                old = self.load(session.session_id)
                if session.attempted_steps[:len(old.attempted_steps)] != old.attempted_steps:
                    raise SessionConflict("Immutable attempt history was modified")
                if (session.manual_id, session.manual_checksum, session.bike_variant, session.edition, session.version_lock) != (old.manual_id, old.manual_checksum, old.bike_variant, old.edition, old.version_lock):
                    raise SessionConflict("Scope/version switch requires a new confirmed session")
            self.db.execute("INSERT INTO sessions VALUES (?, ?, ?)",
                            (session.session_id, session.version, json.dumps(asdict(session), allow_nan=False)))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def close(self):
        self.db.close()
