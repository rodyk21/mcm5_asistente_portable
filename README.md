# MCM5 AI Maintenance Assistant

Asistente tecnico para ingesta, consulta y analisis del historico de la linea MCM5.

## Que incluye

- API con FastAPI
- Base de datos SQLite local
- Ingesta de DDS, RDI, PM Card y MID-RANGE / BMS
- Consulta con proveedores IA:
  - Anthropic / Claude
  - OpenAI / ChatGPT
  - Google / Gemini
  - xAI / Grok
- Fallback a modo local cuando no hay API disponible
- Interfaz web local
- Importacion y analisis de informes Proficy
- Construccion de portable Windows

## Que se sincroniza por Git

El repositorio esta pensado para sincronizar entre equipos lo que realmente conviene mantener:

- codigo fuente
- interfaz web
- scripts de arranque
- configuracion de ejemplo
- build del portable

No se suben al repo:

- `.env`
- `.venv`
- `dist`
- `build`
- bases SQLite locales
- logs
- archivos subidos temporales

Eso evita subir claves privadas, binarios pesados o datos de planta que pueden ser sensibles.

## Estructura esperada de datos

Por defecto la app busca carpetas hermanas del proyecto:

- `dds`
- `14 RDIs`
- `3 BDE (PM card's)`
- `mid-range`

Si en otro equipo quieres otra estructura, puedes ajustarla con variables de entorno.

## Arranque rapido en Windows

1. Crea `.env` a partir de `.env.example` si vas a usar APIs.
2. Ejecuta `iniciar.bat`.
3. La app abrira la interfaz local en el navegador.

## Arranque rapido en macOS o Linux

1. Clona el repo.
2. Crea y activa un entorno virtual:
   `python3 -m venv .venv`
3. Instala dependencias:
   `./.venv/bin/pip install -r requirements.txt`
4. Crea `.env` a partir de `.env.example` si vas a usar APIs.
5. Arranca con:
   `sh iniciar.sh`

El script `iniciar.sh` usa primero `./.venv/bin/python` y, si no existe, prueba `python3` o `python`.

## Modo portable Windows

- Ejecuta `build_portable.ps1` en el PC donde preparas el paquete.
- Se generara la carpeta dentro de `dist`.
- Copia la carpeta completa al PC del trabajo.
- En el PC del trabajo abre `MCM5 AI Assistant.exe`.

La importacion Proficy funciona en local para `.xlsx` y `.csv`. Si el informe viene en `.xls`, conviene reexportarlo a `.xlsx` o `.csv`.

## Variables disponibles en `.env`

- `LLM_PROVIDER=auto`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `GOOGLE_API_KEY`
- `GOOGLE_MODEL`
- `XAI_API_KEY`
- `XAI_MODEL`
- `MCM5_HOST`
- `MCM5_PORT`
- `MCM5_WORKSPACE_DIR`
- `MCM5_DDS_DIR`
- `MCM5_RDI_DIR`
- `MCM5_PM_DIR`
- `MCM5_MIE_DIR`

## Notas

- Si dejas `LLM_PROVIDER=auto`, la aplicacion usa la primera API disponible.
- Tambien puedes elegir el proveedor desde la web.
- Si falla internet o la API, `/consulta` responde en modo local.
- Para Windows de planta, la via recomendada sigue siendo el `.exe` portable.
- Para MacBook, la via recomendada es clonar el repo y ejecutar desde Python.
