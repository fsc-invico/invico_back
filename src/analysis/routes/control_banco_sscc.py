from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ControlBancoSSCCDocument,
    ControlBancoSSCCFullFilter,
    ControlBancoSSCCLiteFilter,
)
from ..services import ControlBancoSSCCService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=ControlBancoSSCCService,
    report_schema=ControlBancoSSCCDocument,
    full_filter_schema=ControlBancoSSCCFullFilter,  # Usa limit/offset
    lite_filter_schema=ControlBancoSSCCLiteFilter,  # No usa limit/offset
    prefix="/controlBanco/sscc",
)

control_banco_sscc_router = factory.get_router()
