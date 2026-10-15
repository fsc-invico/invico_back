__all__ = [
    "SaldosBarriosEvolucionRepositoryDependency",
    "SaldosBarriosEvolucionRepository",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import SaldosBarriosEvolucionDocument


class SaldosBarriosEvolucionRepository(BaseRepository[SaldosBarriosEvolucionDocument]):
    collection_name = "sgv_saldos_barrios_evolucion"
    model = SaldosBarriosEvolucionDocument


SaldosBarriosEvolucionRepositoryDependency = Annotated[
    SaldosBarriosEvolucionRepository, Depends()
]
