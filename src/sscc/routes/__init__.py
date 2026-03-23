__all__ = ["sscc_router"]

from fastapi import APIRouter

from .banco_invico import banco_invico_router
from .banco_invico_sdo_final import banco_invico_sdo_final_router
from .ctas_ctes import ctas_ctes_router

sscc_router = APIRouter(prefix="/sscc", tags=["SSCC"])


sscc_router.include_router(ctas_ctes_router)
sscc_router.include_router(banco_invico_sdo_final_router)
sscc_router.include_router(banco_invico_router)
