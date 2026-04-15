import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from armis_modules.connector_alerts import ArmisAlertsConnector, ArmisAlertsConnectorConfiguration


@pytest.fixture
def connector(module, data_storage):
    c = ArmisAlertsConnector(module=module, data_path=data_storage)
    c.configuration = ArmisAlertsConnectorConfiguration(
        intake_key="test_intake_key",
        polling_interval=5,
    )
    c.log = MagicMock()
    c.log_exception = MagicMock()
    c.push_events_to_intakes = MagicMock()
    return c


def test_push_events(connector):
    """3 alerts from client → push_events_to_intakes called with 3 JSON strings."""
    fake_alerts = [{"alertId": i, "title": f"Alert {i}"} for i in range(3)]

    with (
        patch("armis_modules.connector_alerts.ArmisApiClient") as MockClient,
        patch("armis_modules.connector_alerts.time.sleep"),
        patch.object(type(connector), "running", new_callable=PropertyMock, side_effect=[True, False]),
    ):
        MockClient.return_value.get_alerts.return_value = iter(fake_alerts)

        connector.run()

        connector.push_events_to_intakes.assert_called_once()
        events = connector.push_events_to_intakes.call_args[1]["events"]
        assert len(events) == 3
        for event, alert in zip(events, fake_alerts):
            assert json.loads(event) == alert


def test_no_events_no_push(connector):
    """0 alerts → push_events_to_intakes must NOT be called."""
    with (
        patch("armis_modules.connector_alerts.ArmisApiClient") as MockClient,
        patch("armis_modules.connector_alerts.time.sleep"),
        patch.object(type(connector), "running", new_callable=PropertyMock, side_effect=[True, False]),
    ):
        MockClient.return_value.get_alerts.return_value = iter([])

        connector.run()

        connector.push_events_to_intakes.assert_not_called()


def test_loop_stops_on_running_false(connector):
    """When running is False from the start, the loop body must never execute."""
    with (
        patch("armis_modules.connector_alerts.ArmisApiClient") as MockClient,
        patch.object(type(connector), "running", new_callable=PropertyMock, return_value=False),
    ):
        connector.run()

        MockClient.return_value.get_alerts.assert_not_called()
        connector.push_events_to_intakes.assert_not_called()


def test_error_does_not_crash_loop(connector):
    """An exception in the loop body is caught and logged; loop continues."""
    call_count = 0

    def running_side_effect():
        nonlocal call_count
        call_count += 1
        return call_count <= 2  # True first iteration, False on second check

    with (
        patch("armis_modules.connector_alerts.ArmisApiClient") as MockClient,
        patch("armis_modules.connector_alerts.time.sleep"),
        patch.object(type(connector), "running", new_callable=PropertyMock, side_effect=[True, False]),
    ):
        MockClient.return_value.get_alerts.side_effect = RuntimeError("API down")

        connector.run()

        connector.log.assert_called()
        log_args = connector.log.call_args_list
        error_calls = [c for c in log_args if c[1].get("level") == "error"]
        assert len(error_calls) >= 1
