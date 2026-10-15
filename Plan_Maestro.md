# PLAN MAESTRO: API Backend INVICO (`invico-back`) — FastAPI + MongoDB Atlas (Koyeb)

---

## 1. Contexto y Objetivos

Desarrollar y mantener el backend centralizado **`invico-back`** construido en **Python FastAPI** e instalado/ejecutado en **Koyeb** (disponible públicamente con documentación OpenAPI/Swagger en `[https://fixed-marita-invico-d13e43fa.koyeb.app/docs](https://fixed-marita-invico-d13e43fa.koyeb.app/docs)`).

El backend expone la API para conectar múltiples frontends (aplicaciones Streamlit como `slave_streamlit` o automatizaciones locales) con la base de datos **MongoDB Atlas**, gestionando la autenticación JWT, la lógica de negocio y el acceso a datos por subdominios del organismo (SIIF, SGF, SSCC, Ícaro, Slave, etc.).

---

## 2. Gestión de Entorno y Dependencias (Poetry / PEP 621)

* **Gestor:** Poetry (utilizando estándar `[project]` en `pyproject.toml` con `poetry-core>=2.0.0`).
* **Versión de Python:** `>=3.12`

* **Dependencias Directas:**
* `fastapi[standard]` (`>=0.129.2,<0.130.0`)
* `uvicorn` (`>=0.41.0,<0.42.0`)
* `motor` (`>=3.7.1,<4.0.0`) (Cliente asíncrono para MongoDB)
* `pydantic-mongo` (`>=3.1.0,<4.0.0`)
* `fastapi-jwt[authlib]` (`>=0.3.0,<0.4.0`)
* `passlib[bcrypt]` (`>=1.7,<2.0`) & `bcrypt` (`==4.0.1`)
* `cryptography` (`>=46.0.5,<47.0.0`)
* `pandas` (`>=3.0.1,<4.0.0`), `openpyxl` (`>=3.1.5,<4.0.0`), `gspread` (`>=6.2.1,<7.0.0`)



---

## 3. Arquitectura del Proyecto (`src/`)

El proyecto aplica el principio de **Separación de Responsabilidades (SoC)** y una arquitectura modular por dominios de negocio. Toda la lógica vive dentro de `src/`, y cada submódulo se subdivide en 4 capas clave: **Repositories**, **Routes**, **Schemas** y **Services**.

```text
invico-back/
├── pyproject.toml              # Especificación PEP 621 / Poetry config
├── poetry.lock
├── README.md
├── .env                        # Variables de entorno (MONGODB_URI, JWT_SECRET, etc.)
└── src/
    ├── main.py                 # Instancia principal de FastAPI, CORS, inclusión de routers
    ├── config/                 # Configuración global de la app, variables de entorno y DB
    │   ├── __init__.py
    │   ├── database.py         # Conexión motor/pymongo a MongoDB Atlas
    │   └── settings.py         # Pydantic Settings
    ├── utils/                  # Funciones de soporte transversales (formato, helpers)
    │   ├── __init__.py
    │   └── helpers.py
    ├── analysis/               # Submódulo: Análisis y cruces de información
    │   ├── repositories/
    │   ├── routes/
    │   ├── schemas/
    │   └── services/
    ├── auth/                   # Submódulo: Autenticación, JWT y permisos (RBAC)
    │   ├── repositories/
    │   ├── routes/
    │   ├── schemas/
    │   └── services/
    ├── icaro/                  # Submódulo: Sistema Ícaro
    │   ├── repositories/
    │   ├── routes/
    │   ├── schemas/
    │   └── services/
    ├── sgf/                    # Submódulo: Sistema de Gestión Financiera
    │   ├── repositories/
    │   ├── routes/
    │   ├── schemas/
    │   └── services/
    ├── siif/                   # Submódulo: Sistema de Información Financiera
    │   ├── repositories/
    │   ├── routes/
    │   ├── schemas/
    │   └── services/
    ├── slave/                  # Submódulo: Padrón de Factureros y Honorarios
    │   ├── repositories/
    │   ├── routes/
    │   ├── schemas/
    │   └── services/
    └── sscc/                   # Submódulo: Sistema SSCC
        ├── repositories/
        ├── routes/
        ├── schemas/
        └── services/

```

---

## 4. Patrón de Capas por Submódulo

Cada submódulo operativo (`analysis`, `auth`, `icaro`, `sgf`, `siif`, `slave`, `sscc`) implementa internamente el patrón de 4 capas:

1. **`schemas/`**: Modelos Pydantic para la validación de Requests y formateo de Responses (DTOs).
2. **`repositories/`**: Acceso directo a las colecciones de MongoDB Atlas usando `motor` / `pydantic-mongo`.
3. **`services/`**: Lógica de negocio, cálculos, validaciones cruzadas y orquestación de operaciones.


4. **`routes/`**: Controladores de endpoints FastAPI (`APIRouter`) con inyección de dependencias (autenticación JWT, parámetros de consulta).

---

## 5. Especificaciones de Ruteo y Endpoints (`/docs`)

Las rutas están organizadas por prefijo según su submódulo funcional en FastAPI:

* **`/auth`**: Login, Registro, Refresh Tokens JWT y Gestión de Roles.


* **`/slave`**:
* `POST /slave/factureros` / `GET /slave/factureros/{cuit}` -> Padrón de factureros e imputación de estructura.
* `POST /slave/honorarios` / `GET /slave/honorarios` -> Carga e historial de comprobantes de honorarios.


* **`/siif`**, **`/sgf`**, **`/sscc`**, **`/icaro`**: Endpoints para sincronización e ingesta de reportes/tablas auxiliares desde los frontends y scripts de automatización.


* **`/analysis`**: Consultas agregadas y reportes de controles cruzados presupuestarios.



---

## 6. Reglas de Implementación y Guía para Vibecoding / Antigravity

1. **Respetar la Arquitectura por Dominio:** No colocar lógica de MongoDB directa en las rutas (`routes/`). Toda interacción con la base de datos debe pasar por `repositories/` y ser invocada desde `services/`.


2. **Sincronización con OpenAPI (`/docs`):** Consultar la documentación interactiva en Koyeb para mantener la consistencia entre los schemas de Pydantic del backend y los clientes HTTP (`httpx`) de los frontends Streamlit.


3. **Manejo de Errores y Tipado:** Utilizar Type Hints nativos de Python 3.12 y elevar `HTTPException` con códigos de estado HTTP apropiados desde los endpoints.


4. **Despliegue en Koyeb:** Mantener el comando de arranque de Uvicorn apuntando al módulo `src.main:app`:
```bash
poetry run uvicorn src.main:app --host 0.0.0.0 --port 8000

```