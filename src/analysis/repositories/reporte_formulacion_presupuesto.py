__all__ = [
    "ReporteFormulacionPresupuestoRepositoryDependency",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas.reporte_formulacion import ReporteFormulacionReport


# -------------------------------------------------
class ReporteFormulacionPresupuestoRepository(BaseRepository[ReporteFormulacionReport]):
    collection_name = "reporte_formulacion_presupuesto"
    model = ReporteFormulacionReport


ReporteFormulacionPresupuestoRepositoryDependency = Annotated[
    ReporteFormulacionPresupuestoRepository, Depends()
]
