__all__ = [
    "ControlHonorariosSIIFvsSlaveRepositoryDependency",
    "ControlHonorariosSGFvsSlaveRepositoryDependency",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas.control_honorarios import (
    ControlHonorariosSGFvsSlaveDocument,
    ControlHonorariosSIIFvsSlaveDocument,
)


# -------------------------------------------------
class ControlHonorariosSIIFvsSlaveRepository(
    BaseRepository[ControlHonorariosSIIFvsSlaveDocument]
):
    collection_name = "control_honorarios_siif_vs_slave"
    model = ControlHonorariosSIIFvsSlaveDocument


ControlHonorariosSIIFvsSlaveRepositoryDependency = Annotated[
    ControlHonorariosSIIFvsSlaveRepository, Depends()
]


# -------------------------------------------------
class ControlHonorariosSGFvsSlaveRepository(
    BaseRepository[ControlHonorariosSGFvsSlaveDocument]
):
    collection_name = "control_honorarios_sgf_vs_slave"
    model = ControlHonorariosSGFvsSlaveDocument


ControlHonorariosSGFvsSlaveRepositoryDependency = Annotated[
    ControlHonorariosSGFvsSlaveRepository, Depends()
]
