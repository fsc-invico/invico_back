__all__ = [
    "ReportePlanillometroRepositoryDependency",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas.reporte_planillometro import ReportePlanillometroReport


# -------------------------------------------------
class ReportePlanillometroRepository(BaseRepository[ReportePlanillometroReport]):
    collection_name = "reporte_planillometro"
    model = ReportePlanillometroReport


ReportePlanillometroRepositoryDependency = Annotated[
    ReportePlanillometroRepository, Depends()
]
