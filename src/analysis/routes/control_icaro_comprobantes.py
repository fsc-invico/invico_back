from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ControlIcaroComprobantesDocument,
    ControlIcaroComprobantesFullFilter,
    ControlIcaroComprobantesLiteFilter,
)
from ..services import ControlIcaroComprobantesService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=ControlIcaroComprobantesService,
    report_schema=ControlIcaroComprobantesDocument,
    full_filter_schema=ControlIcaroComprobantesFullFilter,  # Usa limit/offset
    lite_filter_schema=ControlIcaroComprobantesLiteFilter,  # No usa limit/offset
    prefix="/controlIcaro/comprobantes",
)

control_icaro_comprobantes_router = factory.get_router()
