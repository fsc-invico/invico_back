from typing import Annotated

from fastapi import Depends

from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    CargaDocument,
    CargaFullDescSIIF,
    CargaFullFilter,
    CargaLiteFilter,
    CargaReport,
    CargaWithDescProveedor,
)
from ..services import CargaService, CargaServiceDependency  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=CargaService,
    report_schema=CargaDocument,
    full_filter_schema=CargaFullFilter,  # Usa limit/offset
    lite_filter_schema=CargaLiteFilter,  # No usa limit/offset
    prefix="/carga",
)

carga_router = factory.get_router()


# -------------------------------------------------
@carga_router.get(
    "/netoRDEU",
    description="Get All merged with RDEU SIIF",
)
async def neto_rdeu(
    params: Annotated[CargaFullFilter, Depends()],
    service: CargaServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.neto_rdeu(params=params)


# -------------------------------------------------
@carga_router.post("/add_one", response_model=CargaDocument)
async def add_one(
    data: CargaReport,
    service: CargaServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.add_one(data)


# -------------------------------------------------
@carga_router.put("/update_one/{id}", response_model=CargaDocument)
async def update_one(
    id: str,
    data: CargaReport,
    service: CargaServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.update_one_safely(id=id, data=data)


# -------------------------------------------------
@carga_router.delete("/delete_one/{id}", response_model=CargaDocument)
async def delete_one(
    id: str, service: CargaServiceDependency, security: AuthorizationDependency
):
    security.is_admin_or_user_or_raise()
    return await service.delete_one(id=id)


# -------------------------------------------------
@carga_router.get(
    "/withDescProveedores",
    description="Get All Carga with Proveedores's Descriptions",
    response_model=list[CargaWithDescProveedor],
)
async def with_desc_proveedores(
    params: Annotated[CargaFullFilter, Depends()],
    service: CargaServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.with_desc_proveedores(params=params)


# -------------------------------------------------
@carga_router.get(
    "/fullDescSIIF",
    description="Get All Carga with Proveedores's and SIIF Estructruas's Descriptions",
    response_model=list[CargaFullDescSIIF],
)
async def full_desc_siif(
    params: Annotated[CargaFullFilter, Depends()],
    service: CargaServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.full_desc_siif(params=params)


# -------------------------------------------------
@carga_router.get(
    "/groupDescSIIF",
    description="Get grouped Carga data with SIIF Estructruas's Descriptions",
    response_model=list[CargaFullDescSIIF],
)
async def group_desc_siif(
    params: Annotated[CargaFullFilter, Depends()],
    service: CargaServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.group_desc_siif(params=params)
