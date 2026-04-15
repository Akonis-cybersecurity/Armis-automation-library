from typing import List

from pydantic.v1 import BaseModel, Field
from sekoia_automation.action import Action

from armis_modules import ArmisModule
from armis_modules.client import ArmisApiClient


class TagDeviceArguments(BaseModel):
    device_id: int = Field(..., description="Numeric identifier of the Armis device")
    tags: List[str] = Field(..., description="List of tags to add to the device")


class TagDeviceAction(Action):
    name = "Tag Device"
    module: ArmisModule

    def run(self, arguments: TagDeviceArguments) -> dict:
        client = ArmisApiClient(
            instance_url=self.module.configuration.instance_url,
            secret_key=self.module.configuration.secret_key,
        )
        result = client.tag_device(arguments.device_id, arguments.tags)
        return {"success": result.get("success", False), "device_id": arguments.device_id, "tags": arguments.tags}
