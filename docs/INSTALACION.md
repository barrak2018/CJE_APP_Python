# CJE Perfumes — Guía de puesta en marcha del backend

Guía generalizada para levantar la API de CJE Perfumes desde cero en cualquier equipo.

---

## Tabla de contenidos

1. [Prerrequisitos](#1-prerrequisitos)
2. [Paso 1 — Crear la base de datos](#2-paso-1--crear-la-base-de-datos)
3. [Paso 2 — Configurar el entorno virtual](#3-paso-2--configurar-el-entorno-virtual)
4. [Paso 3 — Instalar dependencias](#4-paso-3--instalar-dependencias)
5. [Paso 4 — Configurar el archivo config.json](#5-paso-4--configurar-el-archivo-configjson)
6. [Paso 5 — Ejecutar la API](#6-paso-5--ejecutar-la-api)
7. [Paso 6 — Verificar](#7-paso-6--verificar)
8. [Despliegue y puesta en marcha por escenario](#8-despliegue-y-puesta-en-marcha-por-escenario)
9. [Referencia rápida](#9-referencia-rápida)

---

## 1. Prerrequisitos

| Software | Versión mínima | Verificar |
|---|---|---|
| Python | 3.10+ | `python --version` |
| PostgreSQL | 14+ | `psql --version` |
| pip | Incluido con Python | `pip --version` |

---

## 2. Paso 1 — Crear la base de datos

1. Conectarse a PostgreSQL con un usuario con permisos de administrador:

```bash
psql -U postgres
```

2. Crear la base de datos:

```sql
CREATE DATABASE "CJE";
```

3. Salir de la consola:

```sql
\q
```

4. Ejecutar el script SQL para crear las tablas. Desde la terminal:

```bash
psql -U postgres -d CJE -f SQL/CJE.sql
```

O copiar el contenido de `SQL/CJE.sql` y ejecutarlo dentro de la consola `psql`.

> **Bases ya existentes:** si la BD se creó antes de que existiera el precio por línea,
> ejecutar además (lo agrega `DETALLES_VENTAS.PRECIO_UNITARIO`, que permite fijar el
> subtotal de cada elemento de un combo por separado):
>
> ```sql
> ALTER TABLE public."DETALLES_VENTAS"
>     ADD COLUMN IF NOT EXISTS "PRECIO_UNITARIO" double precision;
> ```

> **Base de datos:** el token JWT protege el acceso a los **datos vía la API**, pero no
> el acceso directo a PostgreSQL (psql/pgAdmin). Para proteger ese acceso se recomienda
> usar un rol dedicado con contraseña fuerte y limitar `listen_addresses` en el servidor.

---

## 3. Paso 2 — Configurar el entorno virtual

Desde la raíz del proyecto:

```bash
# Crear entorno virtual
python -m venv cje_venv

# Activar (Windows)
cje_venv\Scripts\activate

# Activar (macOS/Linux)
source cje_venv/bin/activate
```

---

## 4. Paso 3 — Instalar dependencias

Con el entorno virtual activado:

```bash
pip install fastapi uvicorn sqlalchemy psycopg2-binary python-jose[cryptography] python-multipart
```

| Paquete | Propósito |
|---|---|
| `fastapi` | Framework web para la API REST |
| `uvicorn` | Servidor ASGI para ejecutar FastAPI |
| `sqlalchemy` | ORM para mapear tablas Python ↔ PostgreSQL |
| `psycopg2-binary` | Driver de conexión Python ↔ PostgreSQL |
| `python-jose[cryptography]` | Generación y validación de tokens JWT (autenticación) |
| `python-multipart` | Soporte del formulario OAuth2 de login (`POST /token/`) |

> Si también se usará la **GUI de escritorio**, instalar además:
>
> ```bash
> pip install PySide6 requests
> ```
>
> | Paquete | Propósito |
> |---|---|
> | `PySide6` | Framework Qt para la GUI |
> | `requests` | Cliente HTTP que la GUI usa para llamar a la API |

---

## 5. Paso 4 — Configurar el archivo config.json

Toda la configuración de la API vive en **un solo archivo**: `cje_api/config.json`. Para
comenzar, copiar la plantilla y editar los valores:

```bash
copy cje_api\config.example.json cje_api\config.json
```

Contenido del archivo:

```json
{
  "database": {
    "user": "postgres",
    "password": "Strider-1",
    "host": "localhost",
    "port": 5432,
    "name": "CJE"
  },
  "auth": {
    "api_user": "admin",
    "api_password": "admin123",
    "secret_key": "dev-secret-cambiar-en-produccion",
    "token_expire_minutes": 1440
  },
  "api": {
    "host": "127.0.0.1",
    "port": 8000,
    "reload": true,
    "url": "http://127.0.0.1:8000"
  }
}
```

| Sección | Qué define |
|---|---|
| `database` | Conexión a PostgreSQL (usuario, contraseña, host, puerto, nombre de BD) |
| `auth` | Credenciales del usuario único de la API, clave de firma del JWT y expiración del token (minutos) |
| `api` | `host`/`port`/`reload` con los que `iniciar_servidor.ps1` lanza uvicorn, y `url` (dirección que la GUI usa para llamar a la API) |

**Precedencia (de menor a mayor):** valores por defecto < `config.json` < variables de
entorno. Las variables de entorno (`CJE_DB_*`, `CJE_API_USER`, `CJE_API_PASSWORD`,
`CJE_SECRET_KEY`, `CJE_TOKEN_EXPIRE_MINUTES`, `CJE_API_URL`) siempre ganan si están
definidas, lo que permite sobreescribir una máquina sin editar el archivo.

**Múltiples escenarios:** se puede mantener un archivo por entorno y elegir cuál se usa con
la variable `CJE_CONFIG`:

```bash
# config.dev.json / config.prod.json ...
$env:CJE_CONFIG = "C:\ruta\config.prod.json"
.\iniciar_servidor.ps1
```

> Si `config.json` no existe o el JSON está malformado, la API arranca igual con valores
> por defecto (solo para desarrollo) y lo avisa por consola.

> **Seguridad:** `config.json` contiene secretos (contraseña de la BD, credenciales de la
> API, clave JWT). No debe compartirse ni versionarse (ver `.gitignore`). Para producción
> usar siempre `api_password` y `secret_key` propios.

---

## 6. Paso 5 — Ejecutar la API

Desde la raíz del proyecto, ejecutar el script de inicio (lee `host`, `port` y `reload`
de `cje_api/config.json` y define las credenciales de la API si no existen):

```powershell
.\iniciar_servidor.ps1
```

Equivalente manual, estando en `cje_api/` con el entorno virtual activado:

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

| Parámetro | Descripción |
|---|---|
| `--reload` | Recarga automáticamente al detectar cambios en el código |
| `--host 127.0.0.1` | Escucha solo en la interfaz local (por defecto; ver §8 para redes) |
| `--port 8000` | Puerto de escucha |

La API estará disponible en: `http://127.0.0.1:8000`

Para acceder a la documentación interactiva de Swagger: `http://127.0.0.1:8000/docs`

---

## 7. Paso 6 — Verificar

1. Verificar estado de la API:

```bash
curl http://127.0.0.1:8000/
```

Respuesta esperada:
```json
{"sistema": "CJE Perfumes API", "estado": "Operativo"}
```

2. Verificar conexión a la base de datos:

```bash
curl http://127.0.0.1:8000/db-check
```

Respuesta esperada:
```json
{"database": "Conexión exitosa a PostgreSQL"}
```

3. Obtener un token de acceso (credenciales de desarrollo `admin` / `admin123`):

```bash
curl -X POST http://127.0.0.1:8000/token/ \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin&password=admin123"
```

Respuesta esperada:
```json
{"access_token": "eyJhbGciOi...", "token_type": "bearer"}
```

4. Verificar que los datos exigen el token (sin header debe responder `401`):

```bash
curl http://127.0.0.1:8000/clientes
curl http://127.0.0.1:8000/clientes -H "Authorization: Bearer <token>"
```

5. Abrir la documentación Swagger en el navegador:

```
http://127.0.0.1:8000/docs
```

> En `/docs` usar el botón **Authorize** (icono de candado) con el usuario y contraseña
> para habilitar los endpoints protegidos.

---

## 8. Despliegue y puesta en marcha por escenario

El mismo `config.json` adapta la puesta en marcha a cada escenario. Cambiar los valores y
reiniciar la API; la GUI usa `api.url` para saber dónde está la API.

### Escenario A — Todo en una sola PC (por defecto)

API + PostgreSQL + GUI en el mismo equipo. No requiere cambios: el `config.json` ya trae
`host: "127.0.0.1"` y `url: "http://127.0.0.1:8000"`.

1. `.\iniciar_servidor.ps1` (API en `http://127.0.0.1:8000`).
2. `.\iniciar_gui.ps1` → la GUI encuentra la API sola y pide iniciar sesión.

### Escenario B — Red local (API en un servidor, GUI en otras PCs)

1. En el equipo que sirve la API:
   - `database.host`: la IP/host de PostgreSQL (puede estar en otra máquina de la red).
   - `api.host`: `"0.0.0.0"` (la API escucha en la red, no solo en local).
   - `api.url`: `"http://<IP_del_servidor>:8000"` (la IP por la que las otras PCs lo alcanzan).
2. Abrir el puerto (firewall del servidor) para el puerto de `api.port`.
3. En **cada** PC con GUI: copiar el `cje_api/config.json` (o definir
   `CJE_API_URL=http://<IP>:8000` como variable de entorno) para que la GUI apunte al
   servidor. Las credenciales que recuerda la GUI se guardan localmente en esa PC.
4. Arrancar el servidor con `.\iniciar_servidor.ps1`.

> La base de datos se consulta solo desde el servidor de la API; las GUI nunca tocan
> PostgreSQL directamente.

### Escenario C — Producción / acceso por internet

Mínimos obligatorios antes de exponer la API:

1. **Secretos propios**: `auth.secret_key` (generar una clave aleatoria), `auth.api_password`
   fuerte y `database.password` real. Nunca los valores por defecto.
2. **Sin auto-reload**: `api.reload: false` (evita recargas y reinicios espontáneos).
3. **HTTPS**: exponer la API detrás de un proxy inverso (Nginx, Traefik, IIS) que termine el
   TLS, o usar los parámetros `--ssl-keyfile` / `--ssl-certfile` de uvicorn. La GUI debería
   apuntar a `https://...`.
4. **Expiración del token**: ajustar `auth.token_expire_minutes` a la sesión deseada.
5. **Base de datos**: rol dedicado con permisos mínimos y contraseña fuerte; no exponer el
   puerto de PostgreSQL fuera de la red interna.
6. **Guardar el archivo como `config.prod.json`** y arrancar con `CJE_CONFIG`:

```powershell
$env:CJE_CONFIG = "C:\ruta\config.prod.json"
.\iniciar_servidor.ps1
```

### Resumen de decisiones por escenario

| Opción | A (local) | B (LAN) | C (producción) |
|---|---|---|---|
| `api.host` | `127.0.0.1` | `0.0.0.0` | `0.0.0.0` (detrás de proxy) |
| `api.url` | `http://127.0.0.1:8000` | `http://<IP>:8000` | `https://<dominio>` |
| `api.reload` | `true` | `false` | `false` |
| `auth.secret_key` | dev | propio | propio (aleatorio) |
| `auth.api_password` | dev | propio | propio (fuerte) |
| Puerto firewall | no | sí (8000) | sí (443 vía proxy) |

---

### Estructura del proyecto

```
CJE_APP_Python/
├── .gitignore
├── cje_api/
│   ├── config.json         # Configuración (BD, auth, API) — no versionar
│   ├── config.example.json # Plantilla sin secretos — versionar
│   ├── main.py             # Punto de entrada de la API
│   ├── config.py           # Loader de config.json (precedencia config < env)
│   ├── database.py         # Conexión a PostgreSQL (desde config.json)
│   ├── security.py         # Tokens JWT + dependencia get_current_user
│   ├── models/             # Modelos SQLAlchemy (mapeo de tablas)
│   ├── schemas/            # Esquemas Pydantic (validación)
│   └── routers/            # Endpoints por módulo (auth.py = POST /token)
├── cje_gui/
│   ├── main.py             # Punto de entrada de la GUI (login + credenciales recordadas)
│   ├── config.py           # Loader de api.url para la GUI
│   ├── api_client.py       # Cliente HTTP (login/logout y re-login automático)
│   ├── login_dialog.py     # Diálogo de inicio de sesión
│   ├── dialogs.py          # FormDialog + DecimalSpinBox + parse_decimal
│   ├── cliente_search.py   # SearchBox genérico + ClienteSearchBox + CatalogoSearchBox
│   ├── venta_dialog.py     # Formulario de venta (nueva y edición)
│   ├── main_window.py      # Ventana principal con pestañas y barra de "Cerrar sesión"
│   └── __init__.py         # Marca el paquete de la GUI
├── SQL/
│   └── CJE.sql             # Script de creación de la BD
└── docs/
    ├── README.md          # Referencia de la API
    ├── FLUJO_DATOS.md     # Procesos y flujos
    ├── LOGICA_NEGOCIO.md  # Reglas de negocio
    ├── INSTALACION.md     # Esta guía
    └── GUIA_GUI.md        # Normas para interfaces que usen la API (cualquier tecnología)
```

### Ejecutar la GUI de escritorio

Con la API corriendo (paso 5), la GUI se abre con el script `iniciar_gui.ps1`. Usa
`api.url` de `cje_api/config.json` (o `CJE_API_URL` si está definida) para localizar la
API, por lo que funciona igual en local, en red o contra un servidor remoto (ver §8).

```bash
cd cje_gui
python main.py
```

La ventana principal abre con una pestaña por módulo en este orden: Fletes, Catálogo, Inventario, Clientes, Ventas, Abonos. Al arrancar se pide **iniciar sesión** (usuario/contraseña de la API); si se marca "Recordar credenciales", las próximas aperturas entran directo. El botón **"Cerrar sesión"** de la barra superior olvida las credenciales y cierra el programa. Para construir interfaces (en cualquier tecnología) que consuman esta API, consultar [GUIA_GUI.md](GUIA_GUI.md).

### Endpoints disponibles

| Método | URL | Descripción |
|---|---|---|
| `GET` | `/` | Estado de la API (público) |
| `GET` | `/db-check` | Verificar conexión a BD (público) |
| `POST` | `/token/` | Iniciar sesión y obtener el token JWT (público) |
| `POST` | `/fletes/` | Crear flete |
| `GET` | `/fletes/` | Listar fletes |
| `GET` | `/fletes/{id}` | Obtener flete por ID |
| `PUT` | `/fletes/{id}` | Actualizar flete |
| `DELETE` | `/fletes/{id}` | Eliminar flete |
| `POST` | `/clientes/` | Crear cliente |
| `GET` | `/clientes/` | Listar clientes |
| `GET` | `/clientes/{cedula}` | Obtener cliente por cédula |
| `PUT` | `/clientes/{cedula}` | Actualizar cliente |
| `DELETE` | `/clientes/{cedula}` | Eliminar cliente |
| `POST` | `/catalogo/` | Crear producto |
| `GET` | `/catalogo/` | Listar catálogo |
| `GET` | `/catalogo/{id}` | Obtener producto por ID |
| `PUT` | `/catalogo/{id}` | Actualizar producto |
| `DELETE` | `/catalogo/{id}` | Eliminar producto |
| `POST` | `/inventario/` | Crear ítem de inventario |
| `GET` | `/inventario/` | Listar inventario |
| `GET` | `/inventario/{id}` | Obtener ítem por ID |
| `PUT` | `/inventario/{id}` | Actualizar ítem |
| `DELETE` | `/inventario/{id}` | Eliminar ítem |
| `POST` | `/ventas/` | Crear venta |
| `GET` | `/ventas/` | Listar ventas |
| `GET` | `/ventas/{id}` | Obtener venta por ID |
| `PUT` | `/ventas/{id}` | Editar venta (encabezado + productos, atómico) |
| `DELETE` | `/ventas/{id}` | Eliminar venta |

> Todos los endpoints de datos requieren el header `Authorization: Bearer <token>`.

### Comando rápido de inicio (resumen)

```bash
# 1. Crear BD
psql -U postgres -c 'CREATE DATABASE "CJE";'
psql -U postgres -d CJE -f SQL/CJE.sql

# 2. Entorno virtual + dependencias
python -m venv cje_venv
cje_venv\Scripts\activate
pip install fastapi uvicorn sqlalchemy psycopg2-binary python-jose[cryptography] python-multipart PySide6 requests

# 3. Configuración
copy cje_api\config.example.json cje_api\config.json   # y editar con los datos reales

# 4. Ejecutar (lee config.json)
.\iniciar_servidor.ps1
.\iniciar_gui.ps1
```
