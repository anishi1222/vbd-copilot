from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.api.routers.auth import SECRET_KEY, create_access_token, decode_access_token


def test_access_token_round_trip() -> None:
    claims = {"sub": "test-user", "role": "developer"}

    token = create_access_token(claims)
    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == claims["sub"]
    assert payload["role"] == claims["role"]
    assert "exp" in payload
    assert "exp" not in claims


def test_expired_access_token_is_rejected() -> None:
    token = create_access_token({"sub": "test-user"}, expires_delta=timedelta(minutes=-1))

    assert decode_access_token(token) is None


@pytest.mark.parametrize("token", ["", "not-a-jwt", "invalid.token.signature"])
def test_malformed_access_token_is_rejected(token: str) -> None:
    assert decode_access_token(token) is None


def test_access_token_with_invalid_signature_is_rejected() -> None:
    token = create_access_token({"sub": "test-user"})
    header, payload, signature = token.split(".")
    replacement = "A" if signature[0] != "A" else "B"
    tampered = f"{header}.{payload}.{replacement}{signature[1:]}"

    assert decode_access_token(tampered) is None


@pytest.mark.parametrize("algorithm", ["HS384", "none"])
def test_access_token_with_unexpected_algorithm_is_rejected(algorithm: str) -> None:
    token = jwt.encode(
        {"sub": "test-user", "exp": datetime.now(UTC) + timedelta(minutes=1)},
        SECRET_KEY if algorithm != "none" else None,
        algorithm=algorithm,
    )

    assert decode_access_token(token) is None
