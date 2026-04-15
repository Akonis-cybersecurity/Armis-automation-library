from pydantic.v1 import BaseModel, Field


class ArmisModuleConfiguration(BaseModel):
    instance_url: str = Field(description="URL de l'instance Armis (ex: https://mycompany.armis.com)")
    secret_key: str = Field(
        description="Secret API Key généré dans Settings > API Management",
        secret=True,
    )
