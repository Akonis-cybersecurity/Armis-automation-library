from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from sekoia_automation.storage import PersistentJSON

from armis_modules.trigger_new_alert import OnNewAlertConfiguration, OnNewAlertTrigger


@pytest.fixture
def trigger(module, data_storage):
    t = OnNewAlertTrigger(module=module, data_path=data_storage)
    t.configuration = OnNewAlertConfiguration(
        intake_key="test_intake_key",
        polling_interval=2,
        min_severity="High",
    )
    t.log = MagicMock()
    t.log_exception = MagicMock()
    t.send_event = MagicMock()
    return t


def _alert(alert_id: int, severity: str, minutes_ago: int = 0) -> dict:
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"alertId": alert_id, "title": f"Alert {alert_id}", "severity": severity, "time": ts}


# ---------------------------------------------------------------------------
# Basic event firing
# ---------------------------------------------------------------------------


def test_send_event_on_new_alert(trigger):
    """Two High/Critical alerts → two send_event calls."""
    alerts = [_alert(1, "High"), _alert(2, "Critical")]

    with (
        patch("armis_modules.trigger_new_alert.ArmisApiClient") as MockClient,
        patch("armis_modules.trigger_new_alert.time.sleep"),
        patch.object(type(trigger), "running", new_callable=PropertyMock, side_effect=[True, False]),
    ):
        MockClient.return_value.get_alerts.return_value = iter(alerts)

        trigger.run()

        assert trigger.send_event.call_count == 2
        names = {c[1]["event_name"] for c in trigger.send_event.call_args_list}
        assert "Armis Alert 1" in names
        assert "Armis Alert 2" in names


# ---------------------------------------------------------------------------
# Severity filter
# ---------------------------------------------------------------------------


def test_filter_by_severity_low(trigger):
    """A Low-severity alert with min_severity=High must NOT fire send_event."""
    alerts = [_alert(1, "Low")]

    with (
        patch("armis_modules.trigger_new_alert.ArmisApiClient") as MockClient,
        patch("armis_modules.trigger_new_alert.time.sleep"),
        patch.object(type(trigger), "running", new_callable=PropertyMock, side_effect=[True, False]),
    ):
        MockClient.return_value.get_alerts.return_value = iter(alerts)

        trigger.run()

        trigger.send_event.assert_not_called()


def test_filter_by_severity_medium(trigger):
    """Medium alert with min_severity=High must be filtered out."""
    alerts = [_alert(1, "Medium")]

    with (
        patch("armis_modules.trigger_new_alert.ArmisApiClient") as MockClient,
        patch("armis_modules.trigger_new_alert.time.sleep"),
        patch.object(type(trigger), "running", new_callable=PropertyMock, side_effect=[True, False]),
    ):
        MockClient.return_value.get_alerts.return_value = iter(alerts)

        trigger.run()

        trigger.send_event.assert_not_called()


def test_severity_boundary_exact_match(trigger):
    """Alert with severity equal to min_severity must fire."""
    alerts = [_alert(1, "High")]

    with (
        patch("armis_modules.trigger_new_alert.ArmisApiClient") as MockClient,
        patch("armis_modules.trigger_new_alert.time.sleep"),
        patch.object(type(trigger), "running", new_callable=PropertyMock, side_effect=[True, False]),
    ):
        MockClient.return_value.get_alerts.return_value = iter(alerts)

        trigger.run()

        trigger.send_event.assert_called_once()


# ---------------------------------------------------------------------------
# Cursor / checkpoint
# ---------------------------------------------------------------------------


def test_checkpoint_saved(trigger, data_storage):
    """After a successful poll, last_alert_time must be written to PersistentJSON."""
    with (
        patch("armis_modules.trigger_new_alert.ArmisApiClient") as MockClient,
        patch("armis_modules.trigger_new_alert.time.sleep"),
        patch.object(type(trigger), "running", new_callable=PropertyMock, side_effect=[True, False]),
    ):
        MockClient.return_value.get_alerts.return_value = iter([])

        trigger.run()

        with PersistentJSON("armis_trigger_cursor.json", data_path=data_storage) as cursor:
            assert "last_alert_time" in cursor


def test_already_seen_alert_skipped(trigger, data_storage):
    """An alert whose time is before last_alert_time must not fire send_event."""
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    with PersistentJSON("armis_trigger_cursor.json", data_path=data_storage) as cursor:
        cursor["last_alert_time"] = old_ts

    # Alert time is 2 hours ago — before the cursor
    stale_alert = _alert(99, "Critical", minutes_ago=120)

    with (
        patch("armis_modules.trigger_new_alert.ArmisApiClient") as MockClient,
        patch("armis_modules.trigger_new_alert.time.sleep"),
        patch.object(type(trigger), "running", new_callable=PropertyMock, side_effect=[True, False]),
    ):
        MockClient.return_value.get_alerts.return_value = iter([stale_alert])

        trigger.run()

        trigger.send_event.assert_not_called()


# ---------------------------------------------------------------------------
# Loop control
# ---------------------------------------------------------------------------


def test_loop_stops_on_running_false(trigger):
    """When running is False from the start, the loop body must never execute."""
    with (
        patch("armis_modules.trigger_new_alert.ArmisApiClient") as MockClient,
        patch.object(type(trigger), "running", new_callable=PropertyMock, return_value=False),
    ):
        trigger.run()

        MockClient.return_value.get_alerts.assert_not_called()
        trigger.send_event.assert_not_called()
