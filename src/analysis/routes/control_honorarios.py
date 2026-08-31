from typing import Annotated

from fastapi import APIRouter, Depends

from ...auth.services import AuthorizationDependency
from ..schemas import (
    ControlHonorariosFullFilter,
    ControlHonorariosLiteFilter,
)
from ..services import ControlHonorariosServiceDependency

control_honorarios_router = APIRouter(prefix="/controlHonorarios")


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
    name="Reportes exportables para Control Honorarios - Google Sheets and Excel",
)
async def export(
    params: Annotated[ControlHonorariosLiteFilter, Depends()],
    service: ControlHonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.export(params)
