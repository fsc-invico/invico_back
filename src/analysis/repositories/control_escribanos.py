__all__ = [
    "ControlEscribanosSIIFvsSGFRepositoryDependency",
    "ControlEscribanosSGFvsSSCCRepositoryDependency",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas.control_escribanos import (
    ControlEscribanosSGFvsSSCCDocument,
    ControlEscribanosSIIFvsSGFDocument,
)


# -------------------------------------------------
class ControlEscribanosSIIFvsSGFRepository(
    BaseRepository[ControlEscribanosSIIFvsSGFDocument]
):
    collection_name = "control_escribanos_siif_vs_sgf"
    model = ControlEscribanosSIIFvsSGFDocument


ControlEscribanosSIIFvsSGFRepositoryDependency = Annotated[
    ControlEscribanosSIIFvsSGFRepository, Depends()
]


# -------------------------------------------------
class ControlEscribanosSGFvsSSCCRepository(
    BaseRepository[ControlEscribanosSGFvsSSCCDocument]
):
    collection_name = "control_escribanos_sgf_vs_sscc"
    model = ControlEscribanosSGFvsSSCCDocument


ControlEscribanosSGFvsSSCCRepositoryDependency = Annotated[
    ControlEscribanosSGFvsSSCCRepository, Depends()
]
