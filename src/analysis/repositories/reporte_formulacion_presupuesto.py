__all__ = [
    "ReporteFormulacionPresupuestoRepositoryDependency",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas.reporte_formulacion import ReporteFormulacionPlanillometroReport


# -------------------------------------------------
class ReporteFormulacionPresupuestoRepository(
    BaseRepository[ReporteFormulacionPlanillometroReport]
):
    collection_name = "reporte_formulacion_presupuesto"
    model = ReporteFormulacionPlanillometroReport


ReporteFormulacionPresupuestoRepositoryDependency = Annotated[
    ReporteFormulacionPresupuestoRepository, Depends()
]
