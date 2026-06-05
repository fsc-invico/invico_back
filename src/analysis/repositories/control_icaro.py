__all__ = [
    "ControlIcaroAnualRepositoryDependency",
    "ControlIcaroComprobantesRepositoryDependency",
    "ControlIcaroPa6RepositoryDependency",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas.control_icaro import (
    ControlIcaroAnualDocument,
    ControlIcaroComprobantesDocument,
    ControlIcaroPa6Document,
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
class ControlIcaroPa6Repository(BaseRepository[ControlIcaroPa6Document]):
    collection_name = "control_icaro_pa6"
    model = ControlIcaroPa6Document


ControlIcaroPa6RepositoryDependency = Annotated[ControlIcaroPa6Repository, Depends()]
