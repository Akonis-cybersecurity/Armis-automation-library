from armis_modules import ArmisModule
from armis_modules.actions.get_alert import GetAlertAction
from armis_modules.actions.get_device import GetDeviceAction
from armis_modules.actions.search_devices import SearchDevicesAction
from armis_modules.actions.tag_device import TagDeviceAction
from armis_modules.actions.update_alert_status import UpdateAlertStatusAction
from armis_modules.connector_alerts import ArmisAlertsConnector
from armis_modules.connector_devices import ArmisDevicesConnector
from armis_modules.connector_vulnerabilities import ArmisVulnerabilitiesConnector
from armis_modules.trigger_new_alert import OnNewAlertTrigger

if __name__ == "__main__":
    module = ArmisModule()
    module.register(ArmisAlertsConnector, "pull-armis-alerts")
    module.register(ArmisDevicesConnector, "pull-armis-devices")
    module.register(ArmisVulnerabilitiesConnector, "pull-armis-vulnerabilities")
    module.register(GetDeviceAction, "get-armis-device")
    module.register(GetAlertAction, "get-armis-alert")
    module.register(SearchDevicesAction, "search-armis-devices")
    module.register(UpdateAlertStatusAction, "update-armis-alert-status")
    module.register(TagDeviceAction, "tag-armis-device")
    module.register(OnNewAlertTrigger, "on-new-armis-alert")
    module.run()
