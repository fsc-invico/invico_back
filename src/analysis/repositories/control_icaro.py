__all__ = [
    "ControlIcaroAnualRepositoryDependency",
    "ControlIcaroComprobantesRepositoryDependency",
    "ControlIcaroPA6RepositoryDependency",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas.control_icaro import (
    ControlIcaroAnualDocument,
    ControlIcaroComprobantesDocument,
    ControlIcaroPA6Document,
)


# -------------------------------------------------
class ControlIcaroAnualRepository(BaseRepository[ControlIcaroAnualDocument]):
    collection_name = "control_icaro_anual"
    model = ControlIcaroAnualDocument


ControlIcaroAnualRepositoryDependency = Annotated[
    ControlIcaroAnualRepository, Depends()
]


# -------------------------------------------------
class ControlIcaroComprobantesRepository(
    BaseRepository[ControlIcaroComprobantesDocument]
):
    collection_name = "control_icaro_comprobantes"
    model = ControlIcaroComprobantesDocument


ControlIcaroComprobantesRepositoryDependency = Annotated[
    ControlIcaroComprobantesRepository, Depends()
]


# -------------------------------------------------
class ControlIcaroPA6Repository(BaseRepository[ControlIcaroPA6Document]):
    collection_name = "control_icaro_pa6"
    model = ControlIcaroPA6Document


ControlIcaroPA6RepositoryDependency = Annotated[ControlIcaroPA6Repository, Depends()]
