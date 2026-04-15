# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-04-15
### Added
- Action GetDeviceAction: retrieve a device by ID
- Action GetAlertAction: retrieve an alert by ID
- Action SearchDevicesAction: search devices via ASQ query
- Action UpdateAlertStatusAction: update the status of an alert (Resolved / Suppressed / Unhandled)
- Action TagDeviceAction: add tags to a device
- Trigger OnNewAlertTrigger: start a playbook on new alert with severity filter
- ArmisApiClient: get_device, get_alert, search_devices, update_alert_status, tag_device methods

## [1.0.0] - 2026-04-15
### Added
- Connector ArmisAlertsConnector : polling des alertes (toutes les 5 min)
- Connector ArmisDevicesConnector : polling des devices (toutes les 24h)
- Connector ArmisVulnerabilitiesConnector : polling des vulnerabilities (toutes les 24h)
- Client ArmisApiClient avec gestion automatique du token (refresh 3 min avant expiration)
- Pagination complète sur tous les endpoints
- Retry automatique avec backoff exponentiel (tenacity)
