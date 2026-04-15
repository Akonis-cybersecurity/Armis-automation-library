import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from sekoia_automation.storage import PersistentJSON

from armis_modules.connector_devices import ArmisDevicesConnector, ArmisDevicesConnectorConfiguration


@pytest.fixture
def connector(module, data_storage):
    c = ArmisDevicesConnector(module=module, data_path=data_storage)
    c.configuration = ArmisDevicesConnectorConfiguration(
        intake_key="test_intake_key",
        polling_interval=1440,
    )
    c.log = MagicMock()
    c.log_exception = MagicMock()
    c.push_events_to_intakes = MagicMock()
    return c


def test_push_devices(connector, data_storage):
    """3 devices → push_events_to_intakes called with 3 JSON strings."""
    fake_devices = [{"id": i, "name": f"Device {i}"} for i in range(3)]

    with (
        patch("armis_modules.connector_devices.ArmisApiClient") as MockClient,
        patch("armis_modules.connector_devices.time.sleep"),
        patch.object(type(connector), "running", new_callable=PropertyMock, side_effect=[True, False]),
    ):
        MockClient.return_value.get_devices.return_value = iter(fake_devices)

        connector.run()

        connector.push_events_to_intakes.assert_called_once()
        events = connector.push_events_to_intakes.call_args[1]["events"]
        assert len(events) == 3
        for event, device in zip(events, fake_devices):
            assert json.loads(event) == device


def test_no_devices_no_push(connector):
    """0 devices → push_events_to_intakes must NOT be called."""
    with (
        patch("armis_modules.connector_devices.ArmisApiClient") as MockClient,
        patch("armis_modules.connector_devices.time.sleep"),
        patch.object(type(connector), "running", new_callable=PropertyMock, side_effect=[True, False]),
    ):
        MockClient.return_value.get_devices.return_value = iter([])

        connector.run()

        connector.push_events_to_intakes.assert_not_called()


def test_checkpoint_saved(connector, data_storage):
    """After a successful poll, last_poll_time must be written to PersistentJSON."""
    with (
        patch("armis_modules.connector_devices.ArmisApiClient") as MockClient,
        patch("armis_modules.connector_devices.time.sleep"),
        patch.object(type(connector), "running", new_callable=PropertyMock, side_effect=[True, False]),
    ):
        MockClient.return_value.get_devices.return_value = iter([{"id": 1}])

        connector.run()

        with PersistentJSON("armis_devices_cursor.json", data_path=data_storage) as cursor:
            assert "last_poll_time" in cursor


def test_checkpoint_used_on_second_run(connector, data_storage):
    """When a checkpoint exists, time_frame_hours is computed from last_poll_time."""
    # Pre-populate cursor with a timestamp 48h ago
    from datetime import datetime, timedelta, timezone

    past = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    with PersistentJSON("armis_devices_cursor.json", data_path=data_storage) as cursor:
        cursor["last_poll_time"] = past

    with (
        patch("armis_modules.connector_devices.ArmisApiClient") as MockClient,
        patch("armis_modules.connector_devices.time.sleep"),
        patch.object(type(connector), "running", new_callable=PropertyMock, side_effect=[True, False]),
    ):
        MockClient.return_value.get_devices.return_value = iter([])

        connector.run()

        call_kwargs = MockClient.return_value.get_devices.call_args[1]
        # Should be ~49 hours (48 elapsed + 1 buffer), not the default 24
        assert call_kwargs["time_frame_hours"] >= 48


def test_loop_stops_on_running_false(connector):
    with (
        patch("armis_modules.connector_devices.ArmisApiClient") as MockClient,
        patch.object(type(connector), "running", new_callable=PropertyMock, return_value=False),
    ):
        connector.run()

        MockClient.return_value.get_devices.assert_not_called()
