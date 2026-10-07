import pytest
from app.security import create_token, decode_token, hash_password, verify_password


def test_password_roundtrip():
    h = hash_password("s3cret")
    assert verify_password("s3cret", h) and not verify_password("wrong", h)


def test_jwt_roundtrip_and_tamper():
    t = create_token("alice", "doctor")
    assert decode_token(t)["role"] == "doctor"
    with pytest.raises(Exception):
        decode_token(t[:-2] + "xx")
