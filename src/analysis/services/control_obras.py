__all__ = ["ControlObrasService", "ControlObrasServiceDependency"]

# import os
from dataclasses import dataclass

# from io import BytesIO
from typing import Annotated, List

import numpy as np
import pandas as pd
from fastapi import Depends, HTTPException
from fastapi.responses import StreamingResponse

# from pydantic import ValidationError
from ...config import logger
from ...icaro.schemas import CargaFullFilter
from ...icaro.services import CargaServiceDependency
from ...sgf.schemas import ResumenRendProvFullFilter
from ...sgf.services import ResumenRendProvServiceDependency
from ...sscc.services import CtasCtesServiceDependency
from ...utils import (
    BaseService,
    RouteReturnSchema,
    sanitize_dataframe_for_json_with_datetime,
    sync_validated_to_repository,
    validate_and_extract_data_from_list,
)
from ..repositories import ControlObrasRepositoryDependency
from ..schemas import (
    ControlObrasDocument,
    ControlObrasFullFilter,
    ControlObrasGenerateFilter,
    ControlObrasLiteFilter,
    ControlObrasReport,
)

# Orden de cabecera común a las hojas de SGF e ICARO del export: coloca
# primero los campos compartidos (claves del cruce) para facilitar la
# comparación fila a fila entre ambas tablas en el Excel. Solo se aplican
# las columnas que existan en cada DataFrame.
EXPORT_LEADING_COLUMNS: list[str] = [
    "ejercicio",
    "mes",
    "fecha",
    "cta_cte",
    "cuit",
    "beneficiario",
    "importe_bruto",
]


@dataclass
# -------------------------------------------------
class ControlObrasService(
    BaseService[
        ControlObrasReport,
        ControlObrasDocument,
        ControlObrasFullFilter,
        ControlObrasLiteFilter,
    ]
):
    repository: ControlObrasRepositoryDependency
    resumen_rend_service: ResumenRendProvServiceDependency
    icaro_service: CargaServiceDependency
    cta_cte_service: CtasCtesServiceDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=ControlObrasFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[ControlObrasReport]) -> RouteReturnSchema:
        """Persiste el cruce (snapshot) con borrado idempotente por ejercicio.

        Es la contraparte del ``GET /generate``: el frontend arma el
        cruce on-demand y luego llama aquí para congelarlo en la colección
        ``control_obras`` (patrón generate -> POST de control_recursos /
        control_aporte_empresario).
        """
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ControlObrasReport,
                field_id=[
                    "ejercicio",
                    "mes",
                    "cta_cte",
                    "cuit",
                ],  # Clave de la fila del cruce
            )

            # 🔥 CONTROL CRÍTICO: Si no hay registros válidos, lanzamos un 400 Bad Request.
            # (Asumo que validation_result.validated es una lista vacía o None cuando falla todo)
            if not validation_result.validated:
                # Si validation_result tiene una lista de errores detallados, los exponemos al frontend
                detail_msg = "No se encontraron registros válidos para procesar."
                if hasattr(validation_result, "errors") and validation_result.errors:
                    # Formateamos los primeros errores para no saturar el log pero dar contexto claro
                    detail_msg += f" Errores detectados: {validation_result.errors[:2]}"

                raise HTTPException(status_code=400, detail=detail_msg)

            # 2. Determinar filtro de borrado (Idempotencia)
            # A esta altura ya es 100% seguro que al menos hay un registro válido en el índice [0]
            ejercicio_detectado = validation_result.validated[0].ejercicio
            delete_filter = {"ejercicio": ejercicio_detectado}

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización Control Obras",
                label="Control Obras",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def generate(
        self,
        params: ControlObrasGenerateFilter,
    ) -> List[ControlObrasReport]:
        """Cruce ICARO vs SGF calculado en el backend (on-demand).

        Replica el cómputo que la página ejecutaba en ``GET /compute``:
        suma de ICARO neto de rdeu012 y del bruto del SGF por
        ``[ejercicio, mes, cta_cte, cuit]`` y ``merge outer`` con la
        diferencia entre ambos.

        Lee las colecciones crudas directamente de MongoDB sin
        descargarlas al cliente. El resultado es una vista on-demand: el
        snapshot en la colección ``control_obras`` lo congela el frontend
        con el ``POST`` posterior (patrón generate -> POST de
        control_recursos).

        Args:
            params: Filtro con el ``ejercicio`` a recalcular.

        Returns:
            Lista de filas del cruce validadas como
            ``ControlObrasReport``.

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        compute_params = ControlObrasFullFilter(
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )
        return await self.compute_control_obras(params=compute_params)

    # -------------------------------------------------
    def _align_export_columns(
        self,
        df: pd.DataFrame,
        renames: dict[str, str] | None = None,
    ) -> pd.DataFrame:
        """Reordena las columnas del DataFrame para el export.

        Coloca primero los campos compartidos definidos en
        ``EXPORT_LEADING_COLUMNS`` (solo los que existan en el
        DataFrame) y deja el resto de columnas en su orden original,
        de modo que las hojas de SGF e ICARO tengan una estructura
        similar y se puedan comparar.

        Args:
            df: DataFrame a reordenar.
            renames: Renombrados previos a aplicar (p.ej.
                ``{"importe": "importe_bruto"}`` en ICARO).

        Returns:
            Copia del DataFrame con las columnas reordenadas.
        """
        if df.empty:
            return df

        if renames:
            df = df.rename(columns=renames)

        leading = [
            column for column in EXPORT_LEADING_COLUMNS if column in df.columns
        ]
        remaining = [column for column in df.columns if column not in leading]

        return df.loc[:, leading + remaining]

    # -------------------------------------------------
    async def export(self, params: ControlObrasLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = ControlObrasFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data_sgf = await self.get_sgf_resumend_rend(params=search_params)
        data_icaro = await self.get_icaro_carga_neto_rdeu(params=search_params)

        # El cruce (la tabla que ve el usuario en la página) se exporta
        # desde el snapshot persistido en Mongo; si todavía no existe, se
        # calcula on-demand para no dejar la hoja vacía.
        snapshot = await self.repository.find_with_filter_params(params=search_params)
        data_ctrl_obras = (
            [doc.model_dump(by_alias=True) for doc in snapshot]
            if snapshot
            else await self.compute_control_obras(
                params=search_params, sgf=data_sgf, icaro=data_icaro
            )
        )

        # 3. Usar el método de la clase base. Alineamos las columnas de
        # SGF e ICARO para que ambas hojas compartan la misma cabecera
        # inicial y sea fácil compararlas (en ICARO el importe se llama
        # 'importe': el renombrado es solo para el export, ya que
        # 'compute_control_obras' sigue consumiendo 'importe').
        df_ctrl_obras = pd.DataFrame(data_ctrl_obras)
        df_sgf = self._align_export_columns(pd.DataFrame(data_sgf))
        df_icaro = self._align_export_columns(
            pd.DataFrame(data_icaro), renames={"importe": "importe_bruto"}
        )
        return self.export_to_excel(
            data_pairs=[
                (df_ctrl_obras, "control_mes_cta_cte_cuit_db"),
                (df_sgf, "resumen_rend_cuit"),
                (df_icaro, "icaro_carga_neto_rdeu"),
            ],
            filename="Control Obras.xlsx",
            upload_to_google_sheets=True,
            spreadsheet_key="16v2ovmQnS1v73-WxTOK6b9Tx9DRugGc70ufpjVi-rPA",
        )

    # -------------------------------------------------
    async def get_icaro_carga_neto_rdeu(
        self,
        params: ControlObrasFullFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        icaro_params = CargaFullFilter(
            ejercicio=str(params.ejercicio),
            limit=None,
        )

        data = await self.icaro_service.carga_neto_rdeu(params=icaro_params)
        if not data:
            return []

        # 1. Carga eficiente a DataFrame
        df = pd.DataFrame(data)
        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        # 2. Unificación de Cuenta Corriente
        df = await self.cta_cte_service.cta_cte_unifier(df, "icaro_cta_cte")

        # 3. Aplicamos el limite a la cantidad de registros, si existe
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        # 4. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def get_sgf_resumend_rend(
        self,
        params: ControlObrasFullFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        sgf_params = ResumenRendProvFullFilter(
            ejercicio=str(params.ejercicio),
            limit=None,
        )

        data = await self.resumen_rend_service.unique_obras(params=sgf_params)
        if not data:
            return []

        # 1. Carga eficiente a DataFrame
        df = pd.DataFrame(data)
        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        # 2. Unificación de Cuenta Corriente
        df = await self.cta_cte_service.cta_cte_unifier(df, "sgf_cta_cte")

        # 3. Aplicamos el limite a la cantidad de registros, si existe
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        # 4. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def compute_control_obras(
        self,
        params: ControlObrasFullFilter,
        icaro: list[dict] = None,
        sgf: list[dict] = None,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        group_by = ["ejercicio", "mes", "cta_cte", "cuit"]

        if not icaro:
            icaro = await self.get_icaro_carga_neto_rdeu(params=params)
        icaro = pd.DataFrame(icaro)
        if not icaro.empty:
            icaro = icaro.loc[:, group_by + ["importe"]]
            icaro = icaro.groupby(group_by)["importe"].sum().reset_index()
            icaro = icaro.rename(columns={"importe": "ejecutado_icaro"})
        else:
            icaro = pd.DataFrame(columns=group_by + ["ejecutado_icaro"])
        # print(f"siif.shape: {siif.shape} - siif.head: {siif.head()}")

        if not sgf:
            sgf = await self.get_sgf_resumend_rend(params=params)
        sgf = pd.DataFrame(sgf)
        if not sgf.empty:
            sgf = sgf.loc[:, group_by + ["importe_bruto"]]
            sgf = sgf.groupby(group_by)["importe_bruto"].sum().reset_index()
            sgf = sgf.rename(columns={"importe_bruto": "bruto_sgf"})
        else:
            sgf = pd.DataFrame(columns=group_by + ["bruto_sgf"])
        # print(f"sscc.shape: {sscc.shape} - sscc.head: {sscc.head()}")

        df = pd.merge(icaro, sgf, how="outer", on=group_by)
        df[["ejecutado_icaro", "bruto_sgf"]] = df[
            ["ejecutado_icaro", "bruto_sgf"]
        ].fillna(0)
        df["diferencia"] = df["ejecutado_icaro"] - df["bruto_sgf"]

        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.replace({np.nan: None}).to_dict(orient="records")


ControlObrasServiceDependency = Annotated[ControlObrasService, Depends()]
