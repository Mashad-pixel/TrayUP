"""Supplemental recovery route cases not covered by the canonical recovery suite."""
import re

from app.models.recovery import OtpChallenge, RecoveryRequest


def _mail_code(app):
    message = app.extensions["mail_outbox"][-1]
    return re.search(r"code is (\d{6})", message["body"]).group(1)


def test_recovery_start_requires_a_json_object(anon_client):
    missing = anon_client.post("/api/forgot/start")
    invalid = anon_client.post("/api/forgot/start", json={"identifier": "not-an-email"})

    assert missing.status_code == 400
    assert missing.get_json()["error"]["code"] == "INVALID_JSON"
    assert invalid.status_code == 400
    assert invalid.get_json()["error"]["code"] == "INVALID_IDENTIFIER"


def test_email_identifier_is_normalized_before_delivery(app, anon_client, student):
    response = anon_client.post(
        "/api/forgot/start",
        json={"identifier": f"  {student.email.upper()}  "},
    )

    assert response.status_code == 200
    assert [mail["to"] for mail in app.extensions["mail_outbox"]] == [student.email]
    assert OtpChallenge.query.filter_by(user_id=student.id).count() == 1


def test_resend_alias_retires_the_previous_code(app, anon_client, student):
    anon_client.post("/api/forgot/start", json={"identifier": student.email})
    old_code = _mail_code(app)
    resent = anon_client.post("/api/forgot/resend", json={"identifier": student.email})
    new_code = _mail_code(app)

    assert resent.status_code == 200
    assert len(app.extensions["mail_outbox"]) == 2
    rejected = anon_client.post(
        "/api/forgot/verify",
        json={"identifier": student.email, "otp": old_code},
    )
    accepted = anon_client.post(
        "/api/forgot/verify",
        json={"identifier": student.email, "otp": new_code},
    )
    assert rejected.status_code == 400
    assert accepted.status_code == 200


def test_malformed_code_does_not_consume_the_valid_code(app, anon_client, student):
    anon_client.post("/api/forgot/start", json={"identifier": student.email})
    code = _mail_code(app)

    malformed = anon_client.post(
        "/api/forgot/verify",
        json={"identifier": student.email, "otp": code[:-1]},
    )
    valid = anon_client.post(
        "/api/forgot/verify",
        json={"identifier": student.email, "otp": code},
    )

    assert malformed.status_code == 400
    assert valid.status_code == 200


def test_support_requests_do_not_disclose_whether_an_account_matches(app, anon_client, student):
    payload = {
        "name": "Asha Rao",
        "identifier": student.email,
        "contactEmail": "asha@example.com",
        "createdEst": "March 2025",
        "lastLoginEst": "last month",
        "reason": "I lost access to my old email address.",
        "extra": "",
    }
    known = anon_client.post("/api/recovery/request", json=payload)
    payload["identifier"] = "nobody@example.com"
    unknown = anon_client.post("/api/recovery/request", json=payload)

    assert known.status_code == unknown.status_code == 201
    assert known.get_json()["message"] == unknown.get_json()["message"]
    assert RecoveryRequest.query.count() == 2
