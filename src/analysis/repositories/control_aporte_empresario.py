__all__ = [
    "ControlAporteEmpresarioRepositoryDependency",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas.control_aporte_empresario import (
    ControlAporteEmpresarioDocument,
)


# -------------------------------------------------
class ControlAporteEmpresarioRepository(
    BaseRepository[ControlAporteEmpresarioDocument]
):
    collection_name = "control_aporte_empresario"
    model = ControlAporteEmpresarioDocument


ControlAporteEmpresarioRepositoryDependency = Annotated[
    ControlAporteEmpresarioRepository, Depends()
]
