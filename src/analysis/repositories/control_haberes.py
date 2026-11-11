__all__ = [
    "ControlHaberesRepositoryDependency",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas.control_haberes import (
    ControlHaberesDocument,
)


# -------------------------------------------------
class ControlHaberesRepository(BaseRepository[ControlHaberesDocument]):
    collection_name = "control_haberes"
    model = ControlHaberesDocument


ControlHaberesRepositoryDependency = Annotated[ControlHaberesRepository, Depends()]
