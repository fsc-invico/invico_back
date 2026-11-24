__all__ = [
    "ControlOtrosGastosSiifRepositoryDependency",
    "ControlOtrosGastosSgfRepositoryDependency",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas.control_otros_gastos import (
    ControlOtrosGastosSgfDocument,
    ControlOtrosGastosSiifDocument,
)


# -------------------------------------------------
class ControlOtrosGastosSiifRepository(
    BaseRepository[ControlOtrosGastosSiifDocument]
):
    collection_name = "control_otros_gastos_siif"
    model = ControlOtrosGastosSiifDocument


ControlOtrosGastosSiifRepositoryDependency = Annotated[
    ControlOtrosGastosSiifRepository, Depends()
]


# -------------------------------------------------
class ControlOtrosGastosSgfRepository(BaseRepository[ControlOtrosGastosSgfDocument]):
    collection_name = "control_otros_gastos_sgf"
    model = ControlOtrosGastosSgfDocument


ControlOtrosGastosSgfRepositoryDependency = Annotated[
    ControlOtrosGastosSgfRepository, Depends()
]
