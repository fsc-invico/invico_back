"""Tests de la cascada de ``id_carga`` en ``CargaService.update_one_safely``.

El ``id_carga`` de ``icaro_carga`` se compone como
``{nro_comprobante}{primera letra del tipo}`` (ej: ``00117/25C``). Al editar
el comprobante (cambio de tipo, nro o fecha) el backend recalcula ese valor,
por lo que las colecciones que lo referencian (``icaro_retenciones``, informe
contable y resumen de rendimiento de obras) también deben actualizarse; si no,
los comprobantes quedan huérfanos de sus retenciones.

Cubre:

- Cambio de ``id_carga`` -> cascada ``update_many`` en los tres dependientes.
- Sin cambio de ``id_carga`` -> los dependientes no se tocan.
- ``id_carga`` duplicado -> 400 sin sincronizar.
- Conflicto de cerrojo (``updated_at``) -> 409 sin sincronizar.
- Extracción del ejercicio a partir del ``id_carga``.

Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_carga_update_cascade -v
"""

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import List, Optional, Tuple

from bson import ObjectId
from fastapi import HTTPException

from src.icaro.schemas import CargaReport
from src.icaro.services import CargaService

MONGO_ID = "65f000000000000000000001"
MONGO_ID_DUPLICADO = "65f000000000000000000002"


# -------------------------------------------------
class RepositorioCargaFalso:
    """Repositorio en memoria que replica el contrato de ``CargaRepository``.

    Nota: ``get_one_by_fields`` devuelve el dict crudo (como el repositorio
    real) y ``find_one_and_update`` devuelve un objeto con atributos.
    """

    # -------------------------------------------------
    def __init__(self, doc: Optional[dict], duplicado: Optional[dict] = None) -> None:
        self.doc = doc
        self.duplicado = duplicado
        self.update_filters: List[dict] = []

    # -------------------------------------------------
    async def get_one_by_fields(self, fields: dict) -> Optional[dict]:
        if "id_carga" in fields:  # Consulta de duplicados
            if self.duplicado and self.duplicado["id_carga"] == fields["id_carga"]:
                return self.duplicado
            return None
        if self.doc and fields.get("_id") == self.doc["_id"]:
            return self.doc
        return None

    # -------------------------------------------------
    async def find_one_and_update(
        self, filter: dict, update_data: dict, return_document: bool = True
    ) -> Optional[SimpleNamespace]:
        if not self.doc or filter.get("_id") != self.doc["_id"]:
            return None
        if filter.get("updated_at") != self.doc["updated_at"]:  # El cerrojo
            return None
        self.doc.update(update_data)
        self.update_filters.append(filter)
        return SimpleNamespace(**self.doc)


# -------------------------------------------------
class RepositorioDependienteFalso:
    """Repositorio en memoria que registra las llamadas a ``update_many``."""

    # -------------------------------------------------
    def __init__(self) -> None:
        self.calls: List[Tuple[dict, dict]] = []

    # -------------------------------------------------
    async def update_many(
        self, filter: dict, update_data: dict, upsert: bool = False
    ) -> int:
        self.calls.append((filter, update_data))
        return 1


# -------------------------------------------------
def construir_servicio(
    repo_carga: RepositorioCargaFalso,
    retenciones_repo: RepositorioDependienteFalso,
    informe_repo: RepositorioDependienteFalso,
    resumen_repo: RepositorioDependienteFalso,
) -> CargaService:
    """Instancia el servicio con dependencias simuladas (dataclass)."""
    return CargaService(
        repository=repo_carga,
        rdeu_service=None,
        proveedores_repo=None,
        rf610_service=None,
        retenciones_repo=retenciones_repo,
        informe_contable_repo=informe_repo,
        resumen_rend_obras_repo=resumen_repo,
    )


# -------------------------------------------------
def documento_previo(updated_at: datetime) -> dict:
    """Documento crudo de ``icaro_carga`` con id_carga tipo CYO (…/25C)."""
    return {
        "_id": ObjectId(MONGO_ID),
        "id_carga": "00117/25C",
        "updated_at": updated_at,
    }


# -------------------------------------------------
def carga_report(id_carga: str, updated_at: datetime) -> CargaReport:
    """Payload de edición equivalente al que arma el frontend de Streamlit."""
    return CargaReport(
        ejercicio=2025,
        mes="01/2025",
        fecha=datetime(2025, 1, 15),
        id_carga=id_carga,
        nro_comprobante="00117/25",
        tipo=id_carga[-1],
        fuente="10",
        actividad="11-00-02-79",
        partida="1100",
        cta_cte="10158-8",
        cuit="20632351514",
        importe=1000.0,
        fondo_reparo=0.0,
        avance=50.0,
        desc_obra="Museo",
        updated_at=updated_at,
    )


# -------------------------------------------------
class TestUpdateOneSafelyCascade(unittest.IsolatedAsyncioTestCase):
    """La edición que cambia el id_carga sincroniza las colecciones dependientes."""

    # -------------------------------------------------
    async def test_cambio_de_tipo_sincroniza_id_carga_en_dependientes(self) -> None:
        """Cambia CYO -> REG: retenciones, informe contable y resumen se actualizan."""
        ahora = datetime(2025, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        repo_carga = RepositorioCargaFalso(documento_previo(ahora))
        retenciones = RepositorioDependienteFalso()
        informe = RepositorioDependienteFalso()
        resumen = RepositorioDependienteFalso()
        servicio = construir_servicio(repo_carga, retenciones, informe, resumen)

        data = carga_report("00117/25R", ahora)  # era 00117/25C
        resultado = await servicio.update_one_safely(id=MONGO_ID, data=data)

        # La carga sí se actualizó (cerrojo OK)
        self.assertEqual(resultado.id_carga, "00117/25R")
        self.assertEqual(len(repo_carga.update_filters), 1)

        # Los tres dependientes se actualizaron a partir del id_carga anterior
        for repo in (retenciones, informe, resumen):
            self.assertEqual(len(repo.calls), 1)
            filtro, update_data = repo.calls[0]
            self.assertEqual(filtro, {"id_carga": "00117/25C"})
            self.assertEqual(update_data["id_carga"], "00117/25R")
            self.assertIsInstance(update_data["updated_at"], datetime)

        # Solo retenciones refresca el ejercicio derivado del id_carga
        self.assertEqual(retenciones.calls[0][1]["ejercicio"], 2025)
        self.assertNotIn("ejercicio", informe.calls[0][1])
        self.assertNotIn("ejercicio", resumen.calls[0][1])

    # -------------------------------------------------
    async def test_id_carga_sin_cambios_no_toca_los_dependientes(self) -> None:
        """Si el id_carga no cambió, ninguna colección dependiente se modifica."""
        ahora = datetime(2025, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        repo_carga = RepositorioCargaFalso(documento_previo(ahora))
        retenciones = RepositorioDependienteFalso()
        informe = RepositorioDependienteFalso()
        resumen = RepositorioDependienteFalso()
        servicio = construir_servicio(repo_carga, retenciones, informe, resumen)

        data = carga_report("00117/25C", ahora)  # mismo id_carga
        resultado = await servicio.update_one_safely(id=MONGO_ID, data=data)

        self.assertEqual(resultado.id_carga, "00117/25C")
        self.assertEqual(len(repo_carga.update_filters), 1)  # la carga sí se guardó
        self.assertEqual(retenciones.calls, [])
        self.assertEqual(informe.calls, [])
        self.assertEqual(resumen.calls, [])

    # -------------------------------------------------
    async def test_id_carga_duplicado_rechaza_sin_sincronizar(self) -> None:
        """Un id_carga ya usado por otro comprobante responde 400 y no cascadea."""
        ahora = datetime(2025, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        duplicado = {
            "_id": ObjectId(MONGO_ID_DUPLICADO),
            "id_carga": "00117/25R",
            "updated_at": ahora,
        }
        repo_carga = RepositorioCargaFalso(documento_previo(ahora), duplicado)
        retenciones = RepositorioDependienteFalso()
        informe = RepositorioDependienteFalso()
        resumen = RepositorioDependienteFalso()
        servicio = construir_servicio(repo_carga, retenciones, informe, resumen)

        data = carga_report("00117/25R", ahora)

        with self.assertRaises(HTTPException) as ctx:
            await servicio.update_one_safely(id=MONGO_ID, data=data)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(repo_carga.update_filters, [])  # no se modificó la carga
        self.assertEqual(retenciones.calls, [])
        self.assertEqual(informe.calls, [])
        self.assertEqual(resumen.calls, [])

    # -------------------------------------------------
    async def test_conflicto_de_cerrojo_no_sincronizar(self) -> None:
        """Si otro usuario editó el registro (updated_at cambió) responde 409."""
        ahora = datetime(2025, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        repo_carga = RepositorioCargaFalso(documento_previo(ahora))
        retenciones = RepositorioDependienteFalso()
        informe = RepositorioDependienteFalso()
        resumen = RepositorioDependienteFalso()
        servicio = construir_servicio(repo_carga, retenciones, informe, resumen)

        data = carga_report(
            "00117/25R", ahora + timedelta(hours=1)  # cerrojo desactualizado
        )

        with self.assertRaises(HTTPException) as ctx:
            await servicio.update_one_safely(id=MONGO_ID, data=data)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(repo_carga.update_filters, [])
        self.assertEqual(retenciones.calls, [])
        self.assertEqual(informe.calls, [])
        self.assertEqual(resumen.calls, [])

    # -------------------------------------------------
    def test_ejercicio_from_id_carga(self) -> None:
        """El ejercicio se deriva de la parte /AA del id_carga."""
        self.assertEqual(CargaService._ejercicio_from_id_carga("00544/26C"), 2026)
        self.assertEqual(CargaService._ejercicio_from_id_carga("00117/25R"), 2025)
        self.assertIsNone(CargaService._ejercicio_from_id_carga("sin-barra"))
        self.assertIsNone(CargaService._ejercicio_from_id_carga(""))


# -------------------------------------------------
if __name__ == "__main__":
    unittest.main(verbosity=2)
