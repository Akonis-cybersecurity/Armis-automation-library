from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from armis_modules.actions.get_alert import GetAlertAction
from armis_modules.actions.get_device import GetDeviceAction
from armis_modules.actions.search_devices import SearchDevicesAction
from armis_modules.actions.tag_device import TagDeviceAction
from armis_modules.actions.update_alert_status import UpdateAlertStatusAction

INSTANCE_URL = "https://test.armis.com"
TOKEN = "test_token"
TOKEN_EXPIRY = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()


def _token_resp():
    return {"json": {"data": {"access_token": TOKEN, "expiration_utc": TOKEN_EXPIRY}, "success": True}}


# ---------------------------------------------------------------------------
# GetDeviceAction
# ---------------------------------------------------------------------------


def test_get_device_success(module, requests_mock):
    requests_mock.post(f"{INSTANCE_URL}/api/v1/access_token/", **_token_resp())
    requests_mock.get(
        f"{INSTANCE_URL}/api/v1/devices/123/",
        json={"data": {"id": 123, "name": "PLC-01"}, "success": True},
    )

    action = GetDeviceAction(module=module)
    action.log = MagicMock()
    result = action.run({"device_id": 123})

    assert result == {"id": 123, "name": "PLC-01"}


def test_get_device_not_found(module, requests_mock):
    requests_mock.post(f"{INSTANCE_URL}/api/v1/access_token/", **_token_resp())
    requests_mock.get(f"{INSTANCE_URL}/api/v1/devices/999/", status_code=404)

    action = GetDeviceAction(module=module)
    action.log = MagicMock()
    result = action.run({"device_id": 999})

    assert result == {}
    assert action._error is not None
    assert "999" in action._error


# ---------------------------------------------------------------------------
# GetAlertAction
# ---------------------------------------------------------------------------


def test_get_alert_success(module, requests_mock):
    requests_mock.post(f"{INSTANCE_URL}/api/v1/access_token/", **_token_resp())
    requests_mock.get(
        f"{INSTANCE_URL}/api/v1/alerts/61/",
        json={
            "data": {"alertId": 61, "title": "Suspicious Activity", "severity": "High"},
            "success": True,
        },
    )

    action = GetAlertAction(module=module)
    action.log = MagicMock()
    result = action.run({"alert_id": 61})

    assert result["alertId"] == 61
    assert result["severity"] == "High"


def test_get_alert_not_found(module, requests_mock):
    requests_mock.post(f"{INSTANCE_URL}/api/v1/access_token/", **_token_resp())
    requests_mock.get(f"{INSTANCE_URL}/api/v1/alerts/9999/", status_code=404)

    action = GetAlertAction(module=module)
    action.log = MagicMock()
    result = action.run({"alert_id": 9999})

    assert result == {}
    assert action._error is not None
    assert "9999" in action._error


# ---------------------------------------------------------------------------
# SearchDevicesAction
# ---------------------------------------------------------------------------


def _page(items, next_url=None):
    return {
        "json": {
            "data": {"data": items, "total": 200, "count": len(items), "next": next_url},
            "success": True,
        }
    }


def test_search_devices_returns_list(module, requests_mock):
    requests_mock.post(f"{INSTANCE_URL}/api/v1/access_token/", **_token_resp())
    requests_mock.get(
        f"{INSTANCE_URL}/api/v1/devices/",
        [
            _page([{"id": 1}, {"id": 2}], next_url="/api/v1/devices/?from=2"),
            _page([{"id": 3}], next_url=None),
        ],
    )

    action = SearchDevicesAction(module=module)
    action.log = MagicMock()
    result = action.run({"aql_query": 'category:"IP Camera"', "max_results": 10})

    assert result["total"] == 3
    assert len(result["devices"]) == 3


def test_search_devices_respects_max_results(module, requests_mock):
    requests_mock.post(f"{INSTANCE_URL}/api/v1/access_token/", **_token_resp())
    # First page returns 50 items with a next page available
    requests_mock.get(
        f"{INSTANCE_URL}/api/v1/devices/",
        **_page([{"id": i} for i in range(50)], next_url="/api/v1/devices/?from=50"),
    )

    action = SearchDevicesAction(module=module)
    action.log = MagicMock()
    result = action.run({"aql_query": 'type:"Camera"', "max_results": 50})

    assert result["total"] == 50
    assert len(result["devices"]) == 50
    # Only 1 GET request should have been made (loop stopped at max_results)
    get_calls = [r for r in requests_mock.request_history if r.method == "GET"]
    assert len(get_calls) == 1


# ---------------------------------------------------------------------------
# UpdateAlertStatusAction
# ---------------------------------------------------------------------------


def test_update_alert_status_valid(module, requests_mock):
    requests_mock.post(f"{INSTANCE_URL}/api/v1/access_token/", **_token_resp())
    requests_mock.patch(
        f"{INSTANCE_URL}/api/v1/alerts/61/",
        json={"data": {"alertId": 61, "status": "Resolved"}, "success": True},
    )

    action = UpdateAlertStatusAction(module=module)
    action.log = MagicMock()
    result = action.run({"alert_id": 61, "status": "Resolved"})

    assert result["alertId"] == 61
    assert result["status"] == "Resolved"


def test_update_alert_status_invalid(module, requests_mock):
    action = UpdateAlertStatusAction(module=module)
    action.log = MagicMock()
    result = action.run({"alert_id": 61, "status": "Invalid"})

    assert result == {}
    assert action._error is not None
    assert "Invalid" in action._error
    # No API call should have been made
    assert requests_mock.call_count == 0


# ---------------------------------------------------------------------------
# TagDeviceAction
# ---------------------------------------------------------------------------


def test_tag_device_success(module, requests_mock):
    requests_mock.post(f"{INSTANCE_URL}/api/v1/access_token/", **_token_resp())
    requests_mock.post(
        f"{INSTANCE_URL}/api/v1/devices/42/tags/",
        json={"success": True},
    )

    action = TagDeviceAction(module=module)
    action.log = MagicMock()
    result = action.run({"device_id": 42, "tags": ["critical", "ot-network"]})

    assert result["success"] is True
    assert result["device_id"] == 42
    assert result["tags"] == ["critical", "ot-network"]
