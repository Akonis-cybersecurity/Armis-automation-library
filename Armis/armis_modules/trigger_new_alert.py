import time
from datetime import datetime, timezone

from pydantic.v1 import Field
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON
from sekoia_automation.trigger import Trigger

from armis_modules import ArmisModule
from armis_modules.client import ArmisApiClient

SEVERITY_ORDER: dict[str, int] = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}


class OnNewAlertConfiguration(DefaultConnectorConfiguration):
    polling_interval: int = Field(2, description="Polling interval in minutes")
    min_severity: str = Field("High", description="Minimum severity: Low, Medium, High, Critical")


class OnNewAlertTrigger(Trigger):
    name = "On New Armis Alert"
    module: ArmisModule
    configuration: OnNewAlertConfiguration  # type: ignore[override]

    def _meets_severity(self, alert_severity: str, min_severity: str) -> bool:
        return SEVERITY_ORDER.get(alert_severity, -1) >= SEVERITY_ORDER.get(min_severity, 0)

    def run(self) -> None:
        self.log(message="Armis OnNewAlert Trigger started", level="info")
        client = ArmisApiClient(
            instance_url=self.module.configuration.instance_url,
            secret_key=self.module.configuration.secret_key,
        )
        while self.running:
            try:
                with PersistentJSON("armis_trigger_cursor.json", data_path=self.data_path) as cursor:
                    last_alert_time = cursor.get("last_alert_time")

                    for alert in client.get_alerts(time_frame_minutes=self.configuration.polling_interval):
                        # Skip already-seen alerts based on timestamp
                        if last_alert_time:
                            alert_ts = alert.get("time", "")
                            try:
                                alert_dt = datetime.fromisoformat(alert_ts.replace("Z", "+00:00"))
                                cursor_dt = datetime.fromisoformat(last_alert_time)
                                if alert_dt <= cursor_dt:
                                    continue
                            except (ValueError, AttributeError):
                                pass

                        # Filter by minimum severity
                        if not self._meets_severity(alert.get("severity", "Low"), self.configuration.min_severity):
                            continue

                        self.send_event(
                            event_name=f"Armis Alert {alert['alertId']}",
                            event=alert,
                        )

                    cursor["last_alert_time"] = datetime.now(timezone.utc).isoformat()

            except Exception as e:
                self.log(message=f"Error polling alerts: {e}", level="error")

            time.sleep(self.configuration.polling_interval * 60)
