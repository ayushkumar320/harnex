from agentharness.logging import redact_event


def test_redacts_secret_like_keys_and_values() -> None:
    event = redact_event(
        None,
        "event",
        {
            "api_key": "live-token",
            "message": "contains token value",
            "status": "ok",
        },
    )

    assert event["api_key"] == "[redacted]"
    assert event["message"] == "[redacted]"
    assert event["status"] == "ok"
