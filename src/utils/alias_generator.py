__all__ = ["CamelModel"]

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


# ----------------------------------------
class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,  # Antes era allow_population_by_field_name
        from_attributes=True,  # Para que funcione bien con lo que traes de la DB
    )
