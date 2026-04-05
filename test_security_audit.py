from security_audit import SecurityEventLogger
from security_controls import FileAbusePrevention, FileCircuitBreaker


def test_security_event_logger_round_trip(tmp_path):
    logger = SecurityEventLogger(tmp_path / "security_events.jsonl")

    logger.log_event(
        event_type="api_security",
        action="temporary_block_enforced",
        severity="WARNING",
        actor="pytest",
        fields={"identity": "ip:127.0.0.1", "retry_after_seconds": 12.0},
    )

    events = logger.read_recent_events(limit=10)

    assert len(events) == 1
    assert events[0]["action"] == "temporary_block_enforced"
    assert events[0]["actor"] == "pytest"
    assert events[0]["fields"]["identity"] == "ip:127.0.0.1"


def test_abuse_prevention_clear_identifier_resets_entry(tmp_path):
    abuse = FileAbusePrevention(
        state_path=tmp_path / "api_abuse_state.json",
        threshold=10.0,
        decay_seconds=3600.0,
        block_seconds=30.0,
        max_block_seconds=60.0,
    )

    decision = abuse.record_event("ip:203.0.113.10", 12.0, "EDGE_RATE_LIMITED")

    assert decision.blocked is True
    assert abuse.clear_identifier("ip:203.0.113.10") is True

    after_clear = abuse.inspect("ip:203.0.113.10")

    assert after_clear.blocked is False
    assert after_clear.score == 0.0
    assert after_clear.block_count == 0


def test_circuit_breaker_reset_closes_provider(tmp_path):
    breaker = FileCircuitBreaker(
        state_path=tmp_path / "provider_circuit_breakers.json",
        failure_threshold=2,
        window_seconds=60.0,
        open_seconds=30.0,
        half_open_retry_seconds=1.0,
    )

    breaker.record_failure("gemini_text", "RATE_LIMIT")
    opened = breaker.record_failure("gemini_text", "TIMEOUT")

    assert opened.blocked is True
    assert opened.state == "open"

    reset = breaker.reset("gemini_text")

    assert reset.blocked is False
    assert reset.state == "closed"
    assert reset.failure_count == 0
