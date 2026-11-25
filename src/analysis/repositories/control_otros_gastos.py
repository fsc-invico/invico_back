__all__ = [
    "ControlOtrosGastosSiifRepositoryDependency",
    "ControlOtrosGastosSgfRepositoryDependency",
    "ControlOtrosGastosCruceRepositoryDependency",
    "ControlOtrosGastosCruceMensualRepositoryDependency",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas.control_otros_gastos import (
    ControlOtrosGastosCruceDocument,
    ControlOtrosGastosCruceMensualDocument,
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


# -------------------------------------------------
class ControlOtrosGastosCruceRepository(
    BaseRepository[ControlOtrosGastosCruceDocument]
):
    collection_name = "control_otros_gastos_cruce"
    model = ControlOtrosGastosCruceDocument


ControlOtrosGastosCruceRepositoryDependency = Annotated[
    ControlOtrosGastosCruceRepository, Depends()
]


# -------------------------------------------------
class ControlOtrosGastosCruceMensualRepository(
    BaseRepository[ControlOtrosGastosCruceMensualDocument]
):
    collection_name = "control_otros_gastos_cruce_mensual"
    model = ControlOtrosGastosCruceMensualDocument


ControlOtrosGastosCruceMensualRepositoryDependency = Annotated[
    ControlOtrosGastosCruceMensualRepository, Depends()
]
