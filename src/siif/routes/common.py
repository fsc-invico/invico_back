__all__ = ["common_router"]

from fastapi import APIRouter

from siif.schemas.common import GrupoPartidaStrSIIF

from ..schemas import (
    FuenteFinanciamientoSIIF,
    GrupoControlFinancieroSIIF,
    GrupoPartidaSIIF,
    PartidaPrincipalSIIF,
    TipoComprobanteSIIF,
)

common_router = APIRouter(prefix="")


# -------------------------------------------------
@common_router.get("/tiposComprobantes")
async def list_tipo_comprobantes():
    return [item.value for item in TipoComprobanteSIIF]


# -------------------------------------------------
@common_router.get("/fuentesFinanciamiento")
async def list_fuentes_financiamiento():
    return [item.value for item in FuenteFinanciamientoSIIF]


# -------------------------------------------------
@common_router.get("/gruposControlFinanciero")
async def list_grupos_control_financiero():
    return [item.value for item in GrupoControlFinancieroSIIF]


# -------------------------------------------------
@common_router.get("/gruposPartidas")
async def list_grupos_partidas():
    return [item.value for item in GrupoPartidaSIIF]


# -------------------------------------------------
@common_router.get("/gruposPartidasStr")
async def list_grupos_partidas_str():
    return [item.value for item in GrupoPartidaStrSIIF]


# -------------------------------------------------
@common_router.get("/partidasPrincipales")
async def list_partidas_principales():
    return [item.value for item in PartidaPrincipalSIIF]
