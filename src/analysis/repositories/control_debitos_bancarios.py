__all__ = [
    "ControlDebitosBancariosRepositoryDependency",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas.control_debitos_bancarios import (
    ControlDebitosBancariosDocument,
)


# -------------------------------------------------
class ControlDebitosBancariosRepository(BaseRepository[ControlDebitosBancariosDocument]):
    collection_name = "control_debitos_bancarios"
    model = ControlDebitosBancariosDocument


ControlDebitosBancariosRepositoryDependency = Annotated[
    ControlDebitosBancariosRepository, Depends()
]
