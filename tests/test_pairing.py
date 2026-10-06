from datetime import datetime, timedelta, timezone

import pytest

from edge.pairing import PairingStore


def test_pairing_token_is_random_short_lived_and_one_time():
    now = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
    store = PairingStore(clock=lambda: now[0])
    first = store.create()
    second = store.create()

    assert first.token != second.token
    assert first.expires_at - first.created_at == timedelta(seconds=120)
    assert "token" not in first.public_status()
    assert store.consume(first.token).status == "connected"
    with pytest.raises(ValueError):
        store.consume(first.token)


def test_pairing_expiry_and_disconnect():
    now = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
    store = PairingStore(clock=lambda: now[0])
    session = store.create()
    now[0] += timedelta(seconds=121)
    assert store.get(session.session_id).status == "expired"
    with pytest.raises(ValueError):
        store.consume(session.token)

    active = store.create()
    assert store.disconnect(active.session_id).status == "disconnected"
