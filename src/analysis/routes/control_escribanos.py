from typing import Annotated, Any, List

from fastapi import APIRouter, BackgroundTasks, Depends

from ...auth.services import AuthorizationDependency
from ...utils import RouteReturnSchema
from ..schemas import (
    ControlEscribanosFullFilter,
    ControlEscribanosGenerateFilter,
    ControlEscribanosLiteFilter,
    ControlEscribanosSGFvsSSCCDocument,
    ControlEscribanosSGFvsSSCCReport,
    ControlEscribanosSIIFvsSGFDocument,
    ControlEscribanosSIIFvsSGFReport,
)
from ..services import ControlEscribanosServiceDependency

control_escribanos_router = APIRouter(prefix="/controlEscribanos")


# -------------------------------------------------
@control_escribanos_router.get(
    "/siifVsSgf",
    description="Snapshot persistido del cruce Escribanos SIIF vs SGF",
    response_model=List[ControlEscribanosSIIFvsSGFDocument],
    response_model_exclude_none=True,
)
async def get_siif_vs_sgf(
    params: Annotated[ControlEscribanosFullFilter, Depends()],
    service: ControlEscribanosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_snapshot_siif_vs_sgf(params=params)


# -------------------------------------------------
@control_escribanos_router.post(
    "/siifVsSgf",
    name="Add Many SIIF vs SGF",
    response_model=RouteReturnSchema,
    responses={400: {"description": "Error en la validación de los datos"}},
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "items": {
                            "$ref": "#/components/schemas/ControlEscribanosSIIFvsSGFReport"
                        },
                    }
                }
            }
        }
    },
)
async def add_many_siif_vs_sgf(
    data: List[dict],
    service: ControlEscribanosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.add_many_siif_vs_sgf(data)


# -------------------------------------------------
@control_escribanos_router.delete(
    "/siifVsSgf",
    name="Delete SIIF vs SGF",
    response_model=RouteReturnSchema,
)
async def delete_siif_vs_sgf(
    params: Annotated[ControlEscribanosLiteFilter, Depends()],
    service: ControlEscribanosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.delete_siif_vs_sgf(params)


# -------------------------------------------------
@control_escribanos_router.get(
    "/sgfVsSscc",
    description="Snapshot persistido del cruce Escribanos SGF vs SSCC",
    response_model=List[ControlEscribanosSGFvsSSCCDocument],
    response_model_exclude_none=True,
)
async def get_sgf_vs_sscc(
    params: Annotated[ControlEscribanosFullFilter, Depends()],
    service: ControlEscribanosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_snapshot_sgf_vs_sscc(params=params)


# -------------------------------------------------
@control_escribanos_router.post(
    "/sgfVsSscc",
    name="Add Many SGF vs SSCC",
    response_model=RouteReturnSchema,
    responses={400: {"description": "Error en la validación de los datos"}},
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "items": {
                            "$ref": "#/components/schemas/ControlEscribanosSGFvsSSCCReport"
                        },
                    }
                }
            }
        }
    },
)
async def add_many_sgf_vs_sscc(
    data: List[dict],
    service: ControlEscribanosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.add_many_sgf_vs_sscc(data)


# -------------------------------------------------
@control_escribanos_router.delete(
    "/sgfVsSscc",
    name="Delete SGF vs SSCC",
    response_model=RouteReturnSchema,
)
async def delete_sgf_vs_sscc(
    params: Annotated[ControlEscribanosLiteFilter, Depends()],
    service: ControlEscribanosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.delete_sgf_vs_sscc(params)


# -------------------------------------------------
@control_escribanos_router.get(
    "/generateSIIFVsSgf",
    description=(
        "Cruce Escribanos SIIF vs SGF calculado on-demand por el "
        "backend (sin persistir; el snapshot lo congela el POST)"
    ),
    response_model=List[ControlEscribanosSIIFvsSGFReport],
    response_model_exclude_none=True,
)
async def generate_siif_vs_sgf(
    params: Annotated[ControlEscribanosGenerateFilter, Depends()],
    service: ControlEscribanosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate_siif_vs_sgf(params=params)


# -------------------------------------------------
@control_escribanos_router.get(
    "/generateSGFVsSscc",
    description=(
        "Cruce Escribanos SGF vs SSCC calculado on-demand por el "
        "backend (sin persistir; el snapshot lo congela el POST)"
    ),
    response_model=List[ControlEscribanosSGFvsSSCCReport],
    response_model_exclude_none=True,
)
async def generate_sgf_vs_sscc(
    params: Annotated[ControlEscribanosGenerateFilter, Depends()],
    service: ControlEscribanosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate_sgf_vs_sscc(params=params)


# -------------------------------------------------
@control_escribanos_router.get(
    "/getSIIFEscribanos",
    description="Comprobantes Escribanos SIIF (rcocc31 2113-2-9)",
    response_model_exclude_none=True,
)
async def get_siif_escribanos(
    params: Annotated[ControlEscribanosFullFilter, Depends()],
    service: ControlEscribanosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_siif_escribanos(params=params)


# -------------------------------------------------
@control_escribanos_router.get(
    "/getSGFEscribanos",
    description="Registros de Escribanos en Sist. Gestión Financiera (SGF)",
    response_model_exclude_none=True,
)
async def get_sgf_escribanos(
    params: Annotated[ControlEscribanosFullFilter, Depends()],
    service: ControlEscribanosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_sgf_escribanos(params=params)


# -------------------------------------------------
@control_escribanos_router.get(
    "/getSSCCEscribanos",
    description="Pagos de Escribanos en el banco (SSCC, cta. cte. unificada)",
    response_model_exclude_none=True,
)
async def get_sscc_escribanos(
    params: Annotated[ControlEscribanosFullFilter, Depends()],
    service: ControlEscribanosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_sscc_escribanos(params=params)


# -------------------------------------------------
@control_escribanos_router.get(
    "/export",
    name="Export to Google Sheets (sin archivo Excel)",
)
async def export(
    params: Annotated[ControlEscribanosLiteFilter, Depends()],
    service: ControlEscribanosServiceDependency,
    security: AuthorizationDependency,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    security.is_admin_or_user_or_raise()
    return await service.export(params=params, background_tasks=background_tasks)