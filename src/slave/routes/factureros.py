from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    FacturerosDocument,
    FacturerosFullFilter,
    FacturerosLiteFilter,
)
from ..services import FacturerosService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=FacturerosService,
    report_schema=FacturerosDocument,
    full_filter_schema=FacturerosFullFilter,  # Usa limit/offset
    lite_filter_schema=FacturerosLiteFilter,  # No usa limit/offset
    prefix="/factureros",
)

factureros_router = factory.get_router()
