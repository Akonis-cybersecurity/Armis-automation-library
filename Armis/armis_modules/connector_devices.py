import json
import time
from datetime import datetime, timezone

from pydantic.v1 import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from armis_modules import ArmisModule
from armis_modules.client import ArmisApiClient


class ArmisDevicesConnectorConfiguration(DefaultConnectorConfiguration):
    polling_interval: int = Field(1440, description="Intervalle de polling en minutes (défaut 24h)")


class ArmisDevicesConnector(Connector):
    module: ArmisModule
    configuration: ArmisDevicesConnectorConfiguration

    def run(self) -> None:
        self.log(message="Armis Devices Connector started", level="info")
        client = ArmisApiClient(
            instance_url=self.module.configuration.instance_url,
            secret_key=self.module.configuration.secret_key,
        )
        while self.running:
            try:
                with PersistentJSON("armis_devices_cursor.json", data_path=self.data_path) as cursor:
                    last_poll = cursor.get("last_poll_time")

                    if last_poll:
                        last_poll_dt = datetime.fromisoformat(last_poll)
                        now = datetime.now(timezone.utc)
                        elapsed_hours = (now - last_poll_dt).total_seconds() / 3600
                        time_frame_hours = max(1, int(elapsed_hours) + 1)
                    else:
                        time_frame_hours = max(1, self.configuration.polling_interval // 60)

                    events = []
                    for device in client.get_devices(time_frame_hours=time_frame_hours):
                        events.append(json.dumps(device))

                    if events:
                        self.push_events_to_intakes(events=events)
                        self.log(message=f"Pushed {len(events)} devices", level="info")
                    else:
                        self.log(message="No new devices", level="info")

                    cursor["last_poll_time"] = datetime.now(timezone.utc).isoformat()

            except Exception as e:
                self.log(message=f"Error fetching devices: {e}", level="error")

            time.sleep(self.configuration.polling_interval * 60)
