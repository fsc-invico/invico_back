__all__ = [
    "ControlObrasRepositoryDependency",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas.control_obras import (
    ControlObrasDocument,
)


# -------------------------------------------------
class ControlObrasRepository(BaseRepository[ControlObrasDocument]):
    collection_name = "control_obras"
    model = ControlObrasDocument


ControlObrasRepositoryDependency = Annotated[ControlObrasRepository, Depends()]
