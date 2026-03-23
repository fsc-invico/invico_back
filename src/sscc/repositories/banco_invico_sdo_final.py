__all__ = ["BancoINVICOSdoFinalRepositoryDependency", "BancoINVICOSdoFinalRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import BancoINVICOSdoFinalDocument


class BancoINVICOSdoFinalRepository(BaseRepository[BancoINVICOSdoFinalDocument]):
    collection_name = "sscc_banco_invico_sdo_final"
    model = BancoINVICOSdoFinalDocument


BancoINVICOSdoFinalRepositoryDependency = Annotated[
    BancoINVICOSdoFinalRepository, Depends()
]
