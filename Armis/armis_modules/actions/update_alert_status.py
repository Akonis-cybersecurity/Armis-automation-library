from pydantic.v1 import BaseModel, Field
from sekoia_automation.action import Action

from armis_modules import ArmisModule
from armis_modules.client import ArmisApiClient

VALID_STATUSES = {"Resolved", "Suppressed", "Unhandled"}


class UpdateAlertStatusArguments(BaseModel):
    alert_id: int = Field(..., description="Numeric identifier of the Armis alert")
    status: str = Field(..., description="New status: Resolved, Suppressed or Unhandled")


class UpdateAlertStatusAction(Action):
    name = "Update Alert Status"
    module: ArmisModule

    def run(self, arguments: UpdateAlertStatusArguments) -> dict:
        if arguments.status not in VALID_STATUSES:
            self.error(f"Invalid status '{arguments.status}'. " f"Allowed values: {', '.join(sorted(VALID_STATUSES))}")
            return {}
        client = ArmisApiClient(
            instance_url=self.module.configuration.instance_url,
            secret_key=self.module.configuration.secret_key,
        )
        return client.update_alert_status(arguments.alert_id, arguments.status)
