__all__ = ["BancoINVICORepositoryDependency", "BancoINVICORepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import BancoINVICODocument


class BancoINVICORepository(BaseRepository[BancoINVICODocument]):
    collection_name = "sscc_banco_invico"
    model = BancoINVICODocument


BancoINVICORepositoryDependency = Annotated[BancoINVICORepository, Depends()]
