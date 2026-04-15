import json
import time

from pydantic.v1 import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from armis_modules import ArmisModule
from armis_modules.client import ArmisApiClient


class ArmisAlertsConnectorConfiguration(DefaultConnectorConfiguration):
    polling_interval: int = Field(5, description="Intervalle de polling en minutes")


class ArmisAlertsConnector(Connector):
    module: ArmisModule
    configuration: ArmisAlertsConnectorConfiguration

    def run(self) -> None:
        self.log(message="Armis Alerts Connector started", level="info")
        client = ArmisApiClient(
            instance_url=self.module.configuration.instance_url,
            secret_key=self.module.configuration.secret_key,
        )
        while self.running:
            try:
                events = []
                for alert in client.get_alerts(time_frame_minutes=self.configuration.polling_interval):
                    events.append(json.dumps(alert))

                if events:
                    self.push_events_to_intakes(events=events)
                    self.log(message=f"Pushed {len(events)} alerts", level="info")
                else:
                    self.log(message="No new alerts", level="info")

            except Exception as e:
                self.log(message=f"Error fetching alerts: {e}", level="error")

            time.sleep(self.configuration.polling_interval * 60)
