__all__ = [
    "ControlRecursosRepositoryDependency",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas.control_recursos import (
    ControlRecursosDocument,
)


# -------------------------------------------------
class ControlRecursosRepository(BaseRepository[ControlRecursosDocument]):
    collection_name = "control_recursos"
    model = ControlRecursosDocument


ControlRecursosRepositoryDependency = Annotated[ControlRecursosRepository, Depends()]
