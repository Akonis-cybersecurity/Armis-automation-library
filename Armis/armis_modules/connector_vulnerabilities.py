import json
import time
from datetime import datetime, timedelta, timezone

from pydantic.v1 import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from armis_modules import ArmisModule
from armis_modules.client import ArmisApiClient


class ArmisVulnerabilitiesConnectorConfiguration(DefaultConnectorConfiguration):
    polling_interval: int = Field(1440, description="Intervalle de polling en minutes (défaut 24h)")


class ArmisVulnerabilitiesConnector(Connector):
    module: ArmisModule
    configuration: ArmisVulnerabilitiesConnectorConfiguration

    def run(self) -> None:
        self.log(message="Armis Vulnerabilities Connector started", level="info")
        client = ArmisApiClient(
            instance_url=self.module.configuration.instance_url,
            secret_key=self.module.configuration.secret_key,
        )
        while self.running:
            try:
                with PersistentJSON("armis_vulns_cursor.json", data_path=self.data_path) as cursor:
                    last_detected_after = cursor.get("last_detected_after")

                    if not last_detected_after:
                        last_detected_after = (
                            datetime.now(timezone.utc) - timedelta(minutes=self.configuration.polling_interval)
                        ).isoformat()

                    events = []
                    for vuln in client.get_vulnerabilities(last_detected_after=last_detected_after):
                        events.append(json.dumps(vuln))

                    if events:
                        self.push_events_to_intakes(events=events)
                        self.log(message=f"Pushed {len(events)} vulnerabilities", level="info")
                    else:
                        self.log(message="No new vulnerabilities", level="info")

                    cursor["last_detected_after"] = datetime.now(timezone.utc).isoformat()

            except Exception as e:
                self.log(message=f"Error fetching vulnerabilities: {e}", level="error")

            time.sleep(self.configuration.polling_interval * 60)
