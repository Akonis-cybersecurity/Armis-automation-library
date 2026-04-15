from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import pytest
from sekoia_automation import constants

from armis_modules import ArmisModule
from armis_modules.models import ArmisModuleConfiguration


@pytest.fixture
def data_storage():
    original_storage = constants.DATA_STORAGE
    tmp = mkdtemp()
    constants.DATA_STORAGE = tmp

    yield Path(tmp)

    rmtree(tmp)
    constants.DATA_STORAGE = original_storage


@pytest.fixture
def module():
    m = ArmisModule()
    m.configuration = ArmisModuleConfiguration(
        instance_url="https://test.armis.com",
        secret_key="test_secret_key",
    )
    return m
