__all__ = ["sgf_router"]

from fastapi import APIRouter

from .resumen_rend_obras import resumen_rend_obras_router
from .resumen_rend_prov import resumen_rend_prov_router

sgf_router = APIRouter(prefix="/sgf", tags=["SGF"])


sgf_router.include_router(resumen_rend_obras_router)
sgf_router.include_router(resumen_rend_prov_router)
