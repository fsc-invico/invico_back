__all__ = [
    "ControlViaticosRendicionRepositoryDependency",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas.control_viaticos import (
    ControlViaticosRendicionDocument,
)


# -------------------------------------------------
class ControlViaticosRendicionRepository(
    BaseRepository[ControlViaticosRendicionDocument]
):
    collection_name = "control_viaticos"
    model = ControlViaticosRendicionDocument


ControlViaticosRendicionRepositoryDependency = Annotated[
    ControlViaticosRendicionRepository, Depends()
]
