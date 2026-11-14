from fastapi import HTTPException

from app.auth import _verified_user_from_claims


def test_verified_firebase_claims_are_accepted():
    assert _verified_user_from_claims({
        "uid": "user-123",
        "email": "candidate@example.com",
        "email_verified": True,
    }) == {"uid": "user-123", "email": "candidate@example.com"}


def test_unverified_firebase_claims_are_rejected():
    try:
        _verified_user_from_claims({
            "uid": "user-123",
            "email": "candidate@example.com",
            "email_verified": False,
        })
        assert False, "Expected unverified email to be rejected"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "verify your email" in exc.detail.lower()


def test_missing_email_verified_claim_is_rejected():
    try:
        _verified_user_from_claims({"uid": "user-123", "email": "candidate@example.com"})
        assert False, "Expected missing verification claim to be rejected"
    except HTTPException as exc:
        assert exc.status_code == 403
