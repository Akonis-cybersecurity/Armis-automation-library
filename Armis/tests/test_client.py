from datetime import datetime, timedelta, timezone

import pytest

from armis_modules.client import ArmisApiClient

INSTANCE_URL = "https://test.armis.com"
SECRET_KEY = "test_secret"
TOKEN = "test_bearer_token"
TOKEN_EXPIRY = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()


@pytest.fixture
def client():
    return ArmisApiClient(instance_url=INSTANCE_URL, secret_key=SECRET_KEY)


def _token_response(token=TOKEN, expiry=None):
    return {
        "json": {
            "data": {"access_token": token, "expiration_utc": expiry or TOKEN_EXPIRY},
            "success": True,
        }
    }


def _page_response(items, next_url=None):
    return {
        "json": {
            "data": {
                "data": items,
                "total": 100,
                "count": len(items),
                "next": next_url,
            },
            "success": True,
        }
    }


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------


def test_get_token_success(client, requests_mock):
    requests_mock.post(f"{INSTANCE_URL}/api/v1/access_token/", **_token_response())

    client._get_token()

    assert client._token == TOKEN
    assert client._token_expires_at is not None


def test_token_refresh_before_expiry(client, requests_mock):
    # Token expires in 2 minutes — within 3-minute margin → should refresh
    soon_expiry = (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat()
    client._token = "old_token"
    client._token_expires_at = datetime.fromisoformat(soon_expiry)

    new_expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    requests_mock.post(f"{INSTANCE_URL}/api/v1/access_token/", **_token_response("new_token", new_expiry))

    client._ensure_token()

    assert client._token == "new_token"


def test_token_no_refresh_if_valid(client, requests_mock):
    # Token expires in 10 minutes — outside 3-minute margin → no refresh
    valid_expiry = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    client._token = "valid_token"
    client._token_expires_at = datetime.fromisoformat(valid_expiry)

    client._ensure_token()

    assert client._token == "valid_token"
    assert requests_mock.call_count == 0


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


def test_get_alerts_pagination(client, requests_mock):
    requests_mock.post(f"{INSTANCE_URL}/api/v1/access_token/", **_token_response())
    requests_mock.get(
        f"{INSTANCE_URL}/api/v1/alerts/",
        [
            _page_response([{"alertId": 1}, {"alertId": 2}], next_url="/api/v1/alerts/?from=2"),
            _page_response([{"alertId": 3}], next_url=None),
        ],
    )

    alerts = list(client.get_alerts(time_frame_minutes=5, page_size=2))

    assert len(alerts) == 3
    assert alerts[0]["alertId"] == 1
    assert alerts[1]["alertId"] == 2
    assert alerts[2]["alertId"] == 3


def test_get_devices_pagination(client, requests_mock):
    requests_mock.post(f"{INSTANCE_URL}/api/v1/access_token/", **_token_response())
    requests_mock.get(
        f"{INSTANCE_URL}/api/v1/devices/",
        [
            _page_response([{"id": 10}, {"id": 11}], next_url="/api/v1/devices/?from=2"),
            _page_response([{"id": 12}], next_url=None),
        ],
    )

    devices = list(client.get_devices(time_frame_hours=24, page_size=2))

    assert len(devices) == 3


def test_get_vulnerabilities_single_page(client, requests_mock):
    requests_mock.post(f"{INSTANCE_URL}/api/v1/access_token/", **_token_response())
    requests_mock.get(
        f"{INSTANCE_URL}/api/v1/vulnerabilities/",
        **_page_response([{"cveId": "CVE-2024-0001"}], next_url=None),
    )

    vulns = list(client.get_vulnerabilities(last_detected_after="2024-01-01T00:00:00+00:00"))

    assert len(vulns) == 1
    assert vulns[0]["cveId"] == "CVE-2024-0001"


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------


def test_retry_on_401(client, requests_mock):
    """401 must force a token refresh and succeed on the next attempt."""
    requests_mock.post(
        f"{INSTANCE_URL}/api/v1/access_token/",
        [
            _token_response(TOKEN),
            _token_response("refreshed_token"),
        ],
    )
    requests_mock.get(
        f"{INSTANCE_URL}/api/v1/alerts/",
        [
            {"status_code": 401},
            _page_response([{"alertId": 99}], next_url=None),
        ],
    )

    alerts = list(client.get_alerts(time_frame_minutes=5))

    assert len(alerts) == 1
    assert alerts[0]["alertId"] == 99
    # Token was refreshed after 401
    assert client._token == "refreshed_token"


def test_retry_on_5xx(client, requests_mock):
    """Two 500 errors then a success — tenacity retries up to 3 attempts."""
    requests_mock.post(f"{INSTANCE_URL}/api/v1/access_token/", **_token_response())
    requests_mock.get(
        f"{INSTANCE_URL}/api/v1/alerts/",
        [
            {"status_code": 500},
            {"status_code": 500},
            _page_response([{"alertId": 42}], next_url=None),
        ],
    )

    alerts = list(client.get_alerts(time_frame_minutes=5))

    assert len(alerts) == 1
    assert alerts[0]["alertId"] == 42
