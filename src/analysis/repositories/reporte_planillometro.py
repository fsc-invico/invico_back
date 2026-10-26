__all__ = [
    "ReportePlanillometroRepositoryDependency",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas.reporte_planillometro import ReportePlanillometroDocument


# -------------------------------------------------
class ReportePlanillometroRepository(BaseRepository[ReportePlanillometroDocument]):
    collection_name = "reporte_planillometro"
    model = ReportePlanillometroDocument


ReportePlanillometroRepositoryDependency = Annotated[
    ReportePlanillometroRepository, Depends()
]
