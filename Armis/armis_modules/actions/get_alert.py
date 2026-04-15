import requests
from pydantic.v1 import BaseModel, Field
from sekoia_automation.action import Action

from armis_modules import ArmisModule
from armis_modules.client import ArmisApiClient


class GetAlertArguments(BaseModel):
    alert_id: int = Field(..., description="Numeric identifier of the Armis alert")


class GetAlertAction(Action):
    name = "Get Alert"
    module: ArmisModule

    def run(self, arguments: GetAlertArguments) -> dict:
        client = ArmisApiClient(
            instance_url=self.module.configuration.instance_url,
            secret_key=self.module.configuration.secret_key,
        )
        try:
            return client.get_alert(arguments.alert_id)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                self.error(f"Alert {arguments.alert_id} not found")
                return {}
            raise
