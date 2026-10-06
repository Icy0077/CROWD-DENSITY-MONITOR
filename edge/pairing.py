"""Short-lived, one-use local pairing sessions for phone camera setup."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets
import threading


@dataclass
class PairingSession:
    session_id: str
    token: str
    created_at: datetime
    expires_at: datetime
    status: str = "waiting"
    device: str | None = None

    def public_status(self):
        return {"session_id": self.session_id, "status": self.status,
                "created_at": self.created_at.isoformat(),
                "expires_at": self.expires_at.isoformat(), "device": self.device}


class PairingStore:
    def __init__(self, ttl_seconds=120, clock=None):
        self.ttl_seconds = ttl_seconds
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._sessions = {}
        self._lock = threading.Lock()

    def create(self):
        now = self.clock()
        session = PairingSession(secrets.token_urlsafe(18), secrets.token_urlsafe(32), now,
                                 now + timedelta(seconds=self.ttl_seconds))
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def _get(self, session_id):
        session = self._sessions.get(session_id)
        if not session:
            raise KeyError("Pairing session not found")
        if self.clock() >= session.expires_at and session.status == "waiting":
            session.status = "expired"
        return session

    def get(self, session_id):
        with self._lock:
            return self._get(session_id)

    def find_token(self, token):
        with self._lock:
            for session in self._sessions.values():
                if secrets.compare_digest(session.token, str(token)):
                    return self._get(session.session_id)
        raise KeyError("Pairing token not found")

    def consume(self, token, device="Phone"):
        with self._lock:
            matches = [item for item in self._sessions.values() if secrets.compare_digest(item.token, str(token))]
            if not matches:
                raise KeyError("Pairing token not found")
            session = matches[0]
            self._get(session.session_id)
            if session.status != "waiting":
                raise ValueError("Pairing token is no longer valid")
            session.status = "connected"
            session.device = device
            return session

    def disconnect(self, session_id):
        with self._lock:
            session = self._get(session_id)
            session.status = "disconnected"
            return session
