import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from sekoia_automation.storage import PersistentJSON

from armis_modules.connector_vulnerabilities import (
    ArmisVulnerabilitiesConnector,
    ArmisVulnerabilitiesConnectorConfiguration,
)


@pytest.fixture
def connector(module, data_storage):
    c = ArmisVulnerabilitiesConnector(module=module, data_path=data_storage)
    c.configuration = ArmisVulnerabilitiesConnectorConfiguration(
        intake_key="test_intake_key",
        polling_interval=1440,
    )
    c.log = MagicMock()
    c.log_exception = MagicMock()
    c.push_events_to_intakes = MagicMock()
    return c


def test_push_vulnerabilities(connector):
    """3 vulns → push_events_to_intakes called with 3 JSON strings."""
    fake_vulns = [{"cveId": f"CVE-2024-{i:04d}"} for i in range(3)]

    with (
        patch("armis_modules.connector_vulnerabilities.ArmisApiClient") as MockClient,
        patch("armis_modules.connector_vulnerabilities.time.sleep"),
        patch.object(type(connector), "running", new_callable=PropertyMock, side_effect=[True, False]),
    ):
        MockClient.return_value.get_vulnerabilities.return_value = iter(fake_vulns)

        connector.run()

        connector.push_events_to_intakes.assert_called_once()
        events = connector.push_events_to_intakes.call_args[1]["events"]
        assert len(events) == 3
        for event, vuln in zip(events, fake_vulns):
            assert json.loads(event) == vuln


def test_no_vulns_no_push(connector):
    """0 vulns → push_events_to_intakes must NOT be called."""
    with (
        patch("armis_modules.connector_vulnerabilities.ArmisApiClient") as MockClient,
        patch("armis_modules.connector_vulnerabilities.time.sleep"),
        patch.object(type(connector), "running", new_callable=PropertyMock, side_effect=[True, False]),
    ):
        MockClient.return_value.get_vulnerabilities.return_value = iter([])

        connector.run()

        connector.push_events_to_intakes.assert_not_called()


def test_cursor_saved(connector, data_storage):
    """After a successful poll, last_detected_after must be written to PersistentJSON."""
    with (
        patch("armis_modules.connector_vulnerabilities.ArmisApiClient") as MockClient,
        patch("armis_modules.connector_vulnerabilities.time.sleep"),
        patch.object(type(connector), "running", new_callable=PropertyMock, side_effect=[True, False]),
    ):
        MockClient.return_value.get_vulnerabilities.return_value = iter([{"cveId": "CVE-2024-0001"}])

        connector.run()

        with PersistentJSON("armis_vulns_cursor.json", data_path=data_storage) as cursor:
            assert "last_detected_after" in cursor


def test_cursor_used_on_second_run(connector, data_storage):
    """When a cursor exists, it is passed to get_vulnerabilities as last_detected_after."""
    saved_ts = "2024-01-15T12:00:00+00:00"
    with PersistentJSON("armis_vulns_cursor.json", data_path=data_storage) as cursor:
        cursor["last_detected_after"] = saved_ts

    with (
        patch("armis_modules.connector_vulnerabilities.ArmisApiClient") as MockClient,
        patch("armis_modules.connector_vulnerabilities.time.sleep"),
        patch.object(type(connector), "running", new_callable=PropertyMock, side_effect=[True, False]),
    ):
        MockClient.return_value.get_vulnerabilities.return_value = iter([])

        connector.run()

        call_kwargs = MockClient.return_value.get_vulnerabilities.call_args[1]
        assert call_kwargs["last_detected_after"] == saved_ts


def test_default_cursor_uses_polling_interval(connector, data_storage):
    """When no cursor exists, last_detected_after defaults to now - polling_interval."""
    before = datetime.now(timezone.utc) - timedelta(minutes=connector.configuration.polling_interval + 1)

    with (
        patch("armis_modules.connector_vulnerabilities.ArmisApiClient") as MockClient,
        patch("armis_modules.connector_vulnerabilities.time.sleep"),
        patch.object(type(connector), "running", new_callable=PropertyMock, side_effect=[True, False]),
    ):
        MockClient.return_value.get_vulnerabilities.return_value = iter([])

        connector.run()

        call_kwargs = MockClient.return_value.get_vulnerabilities.call_args[1]
        ts = datetime.fromisoformat(call_kwargs["last_detected_after"])
        assert ts > before


def test_loop_stops_on_running_false(connector):
    with (
        patch("armis_modules.connector_vulnerabilities.ArmisApiClient") as MockClient,
        patch.object(type(connector), "running", new_callable=PropertyMock, return_value=False),
    ):
        connector.run()

        MockClient.return_value.get_vulnerabilities.assert_not_called()
