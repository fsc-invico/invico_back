from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    HonorariosDocument,
    HonorariosFullFilter,
    HonorariosLiteFilter,
)
from ..services import HonorariosService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=HonorariosService,
    report_schema=HonorariosDocument,
    full_filter_schema=HonorariosFullFilter,  # Usa limit/offset
    lite_filter_schema=HonorariosLiteFilter,  # No usa limit/offset
    prefix="/honorarios",
)

honorarios_router = factory.get_router()
