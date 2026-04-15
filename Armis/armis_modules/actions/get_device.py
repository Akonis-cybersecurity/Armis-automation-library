import requests
from pydantic.v1 import BaseModel, Field
from sekoia_automation.action import Action

from armis_modules import ArmisModule
from armis_modules.client import ArmisApiClient


class GetDeviceArguments(BaseModel):
    device_id: int = Field(..., description="Numeric identifier of the Armis device")


class GetDeviceAction(Action):
    name = "Get Device"
    module: ArmisModule

    def run(self, arguments: GetDeviceArguments) -> dict:
        client = ArmisApiClient(
            instance_url=self.module.configuration.instance_url,
            secret_key=self.module.configuration.secret_key,
        )
        try:
            return client.get_device(arguments.device_id)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                self.error(f"Device {arguments.device_id} not found")
                return {}
            raise
