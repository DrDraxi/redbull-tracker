import time

from itsdangerous import URLSafeTimedSerializer

from redbull_api.auth import (
    check_bearer,
    check_cookie,
    make_cookie_value,
)


def test_check_bearer_accepts_correct_token():
    assert check_bearer("Bearer secret123", expected="secret123") is True


def test_check_bearer_rejects_missing_header():
    assert check_bearer(None, expected="secret123") is False


def test_check_bearer_rejects_wrong_token():
    assert check_bearer("Bearer wrong", expected="secret123") is False


def test_check_bearer_rejects_wrong_scheme():
    assert check_bearer("Basic secret123", expected="secret123") is False


def test_make_and_check_cookie_roundtrip():
    secret = "cookie-secret"
    value = make_cookie_value(secret)
    assert check_cookie(value, secret=secret, max_age_seconds=3600) is True


def test_check_cookie_rejects_tampered_value():
    secret = "cookie-secret"
    value = make_cookie_value(secret) + "x"
    assert check_cookie(value, secret=secret, max_age_seconds=3600) is False


def test_check_cookie_rejects_missing_cookie():
    assert check_cookie(None, secret="x", max_age_seconds=3600) is False


def test_check_cookie_rejects_expired():
    secret = "s"
    s = URLSafeTimedSerializer(secret)
    old = s.dumps("authed")
    # itsdangerous truncates age to int seconds and compares with <=, so we
    # need (sleep_int > max_age). Sleep 2.5s with max_age=1 reliably expires.
    time.sleep(2.5)
    assert check_cookie(old, secret=secret, max_age_seconds=1) is False
