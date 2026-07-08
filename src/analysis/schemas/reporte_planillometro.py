__all__ = [
    "ReportePlanillometroFilter",
]


import datetime as dt
from typing import Optional

from pydantic import Field

from ...utils import CamelModel


# -------------------------------------------------
class ReportePlanillometroFilter(CamelModel):
    limit: Optional[int] = Field(100, gte=0)
    ejercicio: Optional[str] = None
    desagregar_desc_subprog: bool = True
    desagregar_obras: bool = False
    desagregar_partida: bool = False
    desagregar_fuente: bool = False
    agregar_acum_2008: bool = True
    date_up_to: Optional[dt.date] = None
    include_pa6: bool = False
