from typing import Annotated, Any, List

from fastapi import APIRouter, BackgroundTasks, Depends

from ...auth.services import AuthorizationDependency
from ...utils import RouteReturnSchema
from ..schemas import (
    ControlHonorariosFullFilter,
    ControlHonorariosGenerateFilter,
    ControlHonorariosLiteFilter,
    ControlHonorariosSGFvsSlaveDocument,
    ControlHonorariosSGFvsSlaveReport,
    ControlHonorariosSIIFvsSlaveDocument,
    ControlHonorariosSIIFvsSlaveReport,
)
from ..services import ControlHonorariosServiceDependency

control_honorarios_router = APIRouter(prefix="/controlHonorarios")


# -------------------------------------------------
@control_honorarios_router.get(
    "/siifVsSlave",
    description="Snapshot persistido del cruce Honorarios SIIF vs Slave",
    response_model=List[ControlHonorariosSIIFvsSlaveDocument],
    response_model_exclude_none=True,
)
async def get_siif_vs_slave(
    params: Annotated[ControlHonorariosFullFilter, Depends()],
    service: ControlHonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_snapshot_siif_vs_slave(params=params)


# -------------------------------------------------
@control_honorarios_router.post(
    "/siifVsSlave",
    name="Add Many SIIF vs Slave",
    response_model=RouteReturnSchema,
    responses={400: {"description": "Error en la validación de los datos"}},
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "items": {
                            "$ref": "#/components/schemas/ControlHonorariosSIIFvsSlaveReport"
                        },
                    }
                }
            }
        }
    },
)
async def add_many_siif_vs_slave(
    data: List[dict],
    service: ControlHonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.add_many_siif_vs_slave(data)


# -------------------------------------------------
@control_honorarios_router.delete(
    "/siifVsSlave",
    name="Delete SIIF vs Slave",
    response_model=RouteReturnSchema,
)
async def delete_siif_vs_slave(
    params: Annotated[ControlHonorariosLiteFilter, Depends()],
    service: ControlHonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.delete_siif_vs_slave(params)


# -------------------------------------------------
@control_honorarios_router.get(
    "/sgfVsSlave",
    description="Snapshot persistido del cruce Honorarios SGF vs Slave",
    response_model=List[ControlHonorariosSGFvsSlaveDocument],
    response_model_exclude_none=True,
)
async def get_sgf_vs_slave(
    params: Annotated[ControlHonorariosFullFilter, Depends()],
    service: ControlHonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_snapshot_sgf_vs_slave(params=params)


# -------------------------------------------------
@control_honorarios_router.post(
    "/sgfVsSlave",
    name="Add Many SGF vs Slave",
    response_model=RouteReturnSchema,
    responses={400: {"description": "Error en la validación de los datos"}},
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "items": {
                            "$ref": "#/components/schemas/ControlHonorariosSGFvsSlaveReport"
                        },
                    }
                }
            }
        }
    },
)
async def add_many_sgf_vs_slave(
    data: List[dict],
    service: ControlHonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.add_many_sgf_vs_slave(data)


# -------------------------------------------------
@control_honorarios_router.delete(
    "/sgfVsSlave",
    name="Delete SGF vs Slave",
    response_model=RouteReturnSchema,
)
async def delete_sgf_vs_slave(
    params: Annotated[ControlHonorariosLiteFilter, Depends()],
    service: ControlHonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.delete_sgf_vs_slave(params)


# -------------------------------------------------
@control_honorarios_router.get(
    "/generateSIIFVsSlave",
    description=(
        "Cruce Honorarios SIIF vs Slave calculado on-demand por el "
        "backend (sin persistir; el snapshot lo congela el POST)"
    ),
    response_model=List[ControlHonorariosSIIFvsSlaveReport],
    response_model_exclude_none=True,
)
async def generate_siif_vs_slave(
    params: Annotated[ControlHonorariosGenerateFilter, Depends()],
    service: ControlHonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate_siif_vs_slave(params=params)


# -------------------------------------------------
@control_honorarios_router.get(
    "/generateSGFVsSlave",
    description=(
        "Cruce Honorarios SGF vs Slave calculado on-demand por el "
        "backend (sin persistir; el snapshot lo congela el POST)"
    ),
    response_model=List[ControlHonorariosSGFvsSlaveReport],
    response_model_exclude_none=True,
)
async def generate_sgf_vs_slave(
    params: Annotated[ControlHonorariosGenerateFilter, Depends()],
    service: ControlHonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate_sgf_vs_slave(params=params)


# -------------------------------------------------
@control_honorarios_router.get(
    "/computeSIIFVsSlave",
    description="Control Cruzado Honorarios SIIF vs Slave",
    # response_model=List[ControlAporteEmpresarioReport],
    response_model_exclude_none=True,
)
async def compute_control_siif_vs_slave(
    params: Annotated[ControlHonorariosFullFilter, Depends()],
    service: ControlHonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.compute_control_siif_vs_slave(params=params)


# -------------------------------------------------
@control_honorarios_router.get(
    "/computeSGFVsSlave",
    description="Control Cruzado Honorarios Sist. Gestión Financiera (SGF) vs Slave",
    # response_model=List[ControlAporteEmpresarioReport],
    response_model_exclude_none=True,
)
async def compute_control_sgf_vs_slave(
    params: Annotated[ControlHonorariosFullFilter, Depends()],
    service: ControlHonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.compute_control_sgf_vs_slave(params=params)


# -------------------------------------------------
@control_honorarios_router.get(
    "/getSIIFHonorarios",
    description="Comprobantes Honorarios SIIF",
    # response_model=List[ControlHaberesReport],
    response_model_exclude_none=True,
)
async def get_siif_honorarios(
    params: Annotated[ControlHonorariosFullFilter, Depends()],
    service: ControlHonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_siif_honorarios(params=params)


# -------------------------------------------------
@control_honorarios_router.get(
    "/getSGFHonorarios",
    description="Registros de Honorarios en Sist. Gestión Financiera (SGF)",
    # response_model=List[ControlHaberesReport],
    response_model_exclude_none=True,
)
async def generate_get_sgf_honorariosbanco(
    params: Annotated[ControlHonorariosFullFilter, Depends()],
    service: ControlHonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_sgf_honorarios(params=params)


# -------------------------------------------------
@control_honorarios_router.get(
    "/getSlaveHonorarios",
    description="Registros de Honorarios en Slave",
    # response_model=List[ControlHaberesReport],
    response_model_exclude_none=True,
)
async def get_slave_honorarios(
    params: Annotated[ControlHonorariosFullFilter, Depends()],
    service: ControlHonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_slave_honorarios(params=params)


# -------------------------------------------------
@control_honorarios_router.get(
    "/export",
    name="Export to Google Sheets (sin archivo Excel)",
)
async def export(
    params: Annotated[ControlHonorariosLiteFilter, Depends()],
    service: ControlHonorariosServiceDependency,
    security: AuthorizationDependency,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    security.is_admin_or_user_or_raise()
    return await service.export(params=params, background_tasks=background_tasks)
