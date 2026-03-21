__all__ = ["PlanillometroHistRepositoryDependency", "PlanillometroHistRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import PlanillometroHistDocument


class PlanillometroHistRepository(BaseRepository[PlanillometroHistDocument]):
    collection_name = "siif_planillometro_hist"
    model = PlanillometroHistDocument


PlanillometroHistRepositoryDependency = Annotated[
    PlanillometroHistRepository, Depends()
]
