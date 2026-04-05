import sys

import security_admin


class _FakeLogger:
    def __init__(self):
        self.events = []

    def read_recent_events(self, limit=200):
        return [{"event_type": "api_security", "action": "temporary_block_enforced", "limit": limit}]

    def log_event(self, **kwargs):
        self.events.append(kwargs)


class _FakeAbuse:
    def __init__(self):
        self.cleared = []

    def list_entries(self, limit=200):
        return [{"identifier": "ip:203.0.113.10", "blocked": True, "score": 10.0}]

    def clear_identifier(self, identifier):
        self.cleared.append(identifier)
        return True


class _FakeBreaker:
    def list_entries(self):
        return [{"provider": "gemini_text", "state": "open", "blocked": True, "failure_count": 4}]

    def reset(self, provider):
        class _Decision:
            def as_metadata(self_inner):
                return {"provider": provider, "state": "closed", "blocked": False}

        return _Decision()


def test_security_admin_events_json(monkeypatch, capsys):
    fake_logger = _FakeLogger()
    monkeypatch.setattr(security_admin, "SecurityEventLogger", lambda: fake_logger)
    monkeypatch.setattr(security_admin, "FileAbusePrevention", lambda: _FakeAbuse())
    monkeypatch.setattr(security_admin, "FileCircuitBreaker", lambda: _FakeBreaker())
    monkeypatch.setattr(sys, "argv", ["security_admin.py", "events", "--limit", "1", "--json"])

    exit_code = security_admin.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "temporary_block_enforced" in captured.out


def test_security_admin_abuse_unblock_logs_admin_action(monkeypatch, capsys):
    fake_logger = _FakeLogger()
    fake_abuse = _FakeAbuse()
    monkeypatch.setattr(security_admin, "SecurityEventLogger", lambda: fake_logger)
    monkeypatch.setattr(security_admin, "FileAbusePrevention", lambda: fake_abuse)
    monkeypatch.setattr(security_admin, "FileCircuitBreaker", lambda: _FakeBreaker())
    monkeypatch.setattr(sys, "argv", ["security_admin.py", "abuse-unblock", "ip:203.0.113.10", "--actor", "pytest-admin"])

    exit_code = security_admin.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Unlocked identity" in captured.out
    assert fake_abuse.cleared == ["ip:203.0.113.10"]
    assert fake_logger.events[0]["action"] == "manual_abuse_unblock"
    assert fake_logger.events[0]["actor"] == "pytest-admin"
