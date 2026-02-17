import os
from typing import Annotated, List

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse

from ...auth.services import OptionalAuthorizationDependency
from ...config import settings
from ...utils import RouteReturnSchema, apply_auto_filter, get_sqlite_path
from ..schemas import Rf602Document, Rf602Filter, Rf602Params
from ..services import Rf602ServiceDependency

rf602_router = APIRouter(prefix="/rf602")

# -------------------------------------------------
@rf602_router.get("/")
async def get_all(
    service: Rf602ServiceDependency,
    # params: Annotated[Rf602Filter, Depends()],
    # response_model=List[Rf602Document]) 
):
    # apply_auto_filter(params=params)
    # return service.get_all(params)
    return await service.get_all()

# -------------------------------------------------
@rf602_router.post("/")
async def add_many(
    # fields: CreateProduct,
    service: Rf602ServiceDependency,
    # security: AuthorizationDependency,
    # response_model=List[RouteReturnSchema]
):
    try:
        # security.is_admin_or_same_seller(product.model_dump()["seller_id"])
        # return service.add_many(fields)
        return await service.add_many()
    except HTTPException as e:
        return JSONResponse(content={"error": e.detail}, status_code=e.status_code)

# -------------------------------------------------
@rf602_router.delete("/")
# @rf602_router.delete("/{ejercicio}")
async def delete_many(
    # ejercicio: str,
    service: Rf602ServiceDependency,
    # security: AuthorizationDependency,
):
    try:
        # security.is_admin_or_same_user(id)
        # return service.delete_many(ejercicio)
        return service.delete_many()
    except HTTPException as e:
        return JSONResponse(content={"error": e.detail}, status_code=e.status_code)


# -------------------------------------------------
@rf602_router.get(
    "/export",
    summary="Descarga los registros rf602 como archivo .xlsx",
    response_description="Archivo Excel con los registros solicitados",
)
async def export_rf602_from_db(service: Rf602ServiceDependency, ejercicio: int = None):
    return await service.export_rf602_from_db(ejercicio)
