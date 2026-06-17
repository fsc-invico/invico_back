__all__ = [
    "ControlBancoCruzadoRepositoryDependency",
    "ControlBancoSIIFRepositoryDependency",
    "ControlBancoSSCCRepositoryDependency",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas.control_banco import (
    ControlBancoCruzadoDocument,
    ControlBancoSIIFDocument,
    ControlBancoSSCCDocument,
)


# -------------------------------------------------
class ControlBancoCruzadoRepository(BaseRepository[ControlBancoCruzadoDocument]):
    collection_name = "control_banco_cruzado"
    model = ControlBancoCruzadoDocument


ControlBancoCruzadoRepositoryDependency = Annotated[
    ControlBancoCruzadoRepository, Depends()
]


# -------------------------------------------------
class ControlBancoSIIFRepository(BaseRepository[ControlBancoSIIFDocument]):
    collection_name = "control_banco_siif"
    model = ControlBancoSIIFDocument


ControlBancoSIIFRepositoryDependency = Annotated[ControlBancoSIIFRepository, Depends()]


# -------------------------------------------------
class ControlBancoSSCCRepository(BaseRepository[ControlBancoSSCCDocument]):
    collection_name = "control_banco_sscc"
    model = ControlBancoSSCCDocument


ControlBancoSSCCRepositoryDependency = Annotated[ControlBancoSSCCRepository, Depends()]
