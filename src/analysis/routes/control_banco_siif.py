from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ControlBancoSIIFDocument,
    ControlBancoSIIFFullFilter,
    ControlBancoSIIFLiteFilter,
)
from ..services import ControlBancoSIIFService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=ControlBancoSIIFService,
    report_schema=ControlBancoSIIFDocument,
    full_filter_schema=ControlBancoSIIFFullFilter,  # Usa limit/offset
    lite_filter_schema=ControlBancoSIIFLiteFilter,  # No usa limit/offset
    prefix="/controlBanco/siif",
)

control_banco_siif_router = factory.get_router()
