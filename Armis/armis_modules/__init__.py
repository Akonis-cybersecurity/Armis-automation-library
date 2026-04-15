from sekoia_automation.module import Module

from armis_modules.models import ArmisModuleConfiguration


class ArmisModule(Module):
    configuration: ArmisModuleConfiguration
