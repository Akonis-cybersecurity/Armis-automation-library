from pydantic.v1 import BaseModel, Field
from sekoia_automation.action import Action

from armis_modules import ArmisModule
from armis_modules.client import ArmisApiClient


class SearchDevicesArguments(BaseModel):
    aql_query: str = Field(..., description='Armis ASQ query (e.g. ip:"1.2.3.4")')
    max_results: int = Field(100, description="Maximum number of results to return")


class SearchDevicesAction(Action):
    name = "Search Devices"
    module: ArmisModule

    def run(self, arguments: SearchDevicesArguments) -> dict:
        client = ArmisApiClient(
            instance_url=self.module.configuration.instance_url,
            secret_key=self.module.configuration.secret_key,
        )
        devices = client.search_devices(
            aql_query=arguments.aql_query,
            max_results=arguments.max_results,
        )
        return {"devices": devices, "total": len(devices)}
