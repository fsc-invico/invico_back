# AGENTS.md: Estándares de Calidad y Arquitectura de IA

Este documento establece las reglas fundamentales, restricciones y estándares de diseño para cualquier asistente de IA (Antigravity, Cursor, Copilot, etc.) que trabaje en la base de código de **`invico-back`**.

---

## 1. Separación Estricta de Responsabilidades (SoC) por Capas

El proyecto está estructurado dentro de `src/` por submódulos de dominio (`slave`, `siif`, `sgf`, `auth`, `sscc`, `icaro`, `analysis`). Cada submódulo debe respetar la siguiente división de responsabilidades:

* **`schemas/` (Modelos Pydantic / DTOs):**
* Declaración estricta de validación para solicitudes y respuestas HTTP.
* **Prohibido:** Importar clientes de base de datos (`motor`, `pymongo`) o llamar a servicios/rutas dentro de los esquemas.


* **`repositories/` (Capa de Acceso a Datos - MongoDB):**
* Encargada exclusivamente de ejecutar consultas, inserciones y actualizaciones contra MongoDB Atlas utilizando `motor` / `pydantic-mongo`.
* **Prohibido:** Manejar excepciones HTTP (`HTTPException`) o depender de objetos de FastAPI (`Request`, `Response`).


* **`services/` (Lógica de Negocio):**
* Orquesta las operaciones de negocio, validaciones cruzadas, cálculos y transformación de datos.
* Consume la capa de `repositories/`.
* **Prohibido:** Definir rutas o decoradores `@router` de FastAPI.


* **`routes/` (Controladores API / FastAPI):**
* Define los endpoints, parámetros de ruta, query params y middlewares de autenticación JWT.
* Delega la lógica de ejecución a la capa `services/`.
* Transforma excepciones de negocio en respuestas `HTTPException` con sus correspondientes códigos HTTP (`400`, `401`, `403`, `404`, `500`).



---

## 2. Estilo de Código Python y Buenas Prácticas (PEP 8)

* **Compatibilidad:** Código escrito exclusivamente para Python 3.12+.
* **Formateo:** Cumplimiento estricto de PEP 8 (4 espacios de sangría por nivel).
* **Nombres:**
* `snake_case` para variables, funciones, métodos y nombres de archivos.
* `CamelCase` para clases y esquemas de Pydantic.
* `UPPER_CASE` para constantes y variables de entorno.
* **Prohibido:** Uso de nombres genéricos de una sola letra (ej. `x`, `d`, `e`), salvo en *list comprehensions* concisas.


* **Tipado Estático Obligatorio (Type Hints):**
* Todas las firmas de funciones, métodos y handlers de endpoints **deben** incluir anotaciones de tipo explícitas (`str`, `int`, `dict`, `list[T]`, `Optional[T]`).



---

## 3. Manejo Riguroso de Errores y Excepciones Async

* **Prohibido Silenciar Errores:** Queda terminantemente prohibido usar bloques `try...except` vacíos, `except Exception: pass`, o capturas genéricas que oculten fallos de conexión a MongoDB.
* **Propagación Controlada:**
1. En `repositories/`: Capturar errores específicos de base de datos (`pymongo.errors.PyMongoError`) y registrar los logs.
2. En `services/`: Convertir errores de persistencia en excepciones de dominio/negocio.
3. En `routes/`: Capturar las excepciones y retornar respuestas estructuradas vía `fastapi.HTTPException`.



---

## 4. Gestión de Dependencias y Entorno (Poetry / PEP 621)

* Las dependencias se gestionan **únicamente** con Poetry (`pyproject.toml`).
* Para añadir o modificar librerías, usar exclusivamente comandos de Poetry (ej. `poetry add <paquete>`).
* **Prohibido:** Modificar manualmente `poetry.lock` o instalar paquetes con `pip` directo fuera del entorno virtual.

---

## 5. Control de Cambios y Git (Límites del Agente)

* Queda **estrictamente prohibido** ejecutar comandos de Git destructivos o de publicación autónoma (`git add`, `git commit`, `git push`, `git rebase`, `git reset --hard`) sin la confirmación y autorización previa del usuario.