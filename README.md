# MCM5 AI Maintenance Assistant

Backend inicial para ingesta y consulta del historico de la linea MCM5.

## Que incluye esta primera version

- API con FastAPI
- Base de datos SQLite local
- Ingesta de DDS, RDI, PM Card y MID-RANGE / BMS
- Exclusión automática de `OBSOLETOS`, plantillas y copias
- Endpoints básicos de ingesta, consulta, feedback y alertas
- Selector de proveedor IA:
  - Anthropic / Claude
  - OpenAI / ChatGPT
  - Google / Gemini
  - xAI / Grok

## Estructura esperada de datos

El backend busca por defecto estas carpetas hermanas del proyecto:

- `D:\trabajo\dds`
- `D:\trabajo\14 RDIs`
- `D:\trabajo\3 BDE (PM card's)`
- `D:\trabajo\mid-range`

## Arranque rapido

1. Ejecuta `configurar_apis.bat` si quieres dejar APIs configuradas.
2. Ejecuta `iniciar.bat`.
3. La aplicacion lanzara el interfaz en tu navegador sin depender de `uvicorn` manual ni de comandos adicionales.

## Modo portable

- Ejecuta `build_portable.ps1` en el PC donde preparas el paquete.
- Se generara `dist\MCM5_AI_Assistant_Portable`.
- Copia esa carpeta completa al PC del trabajo.
- En el PC del trabajo abre `MCM5 AI Assistant.exe`.
- El ejecutable ya no depende de `bat` ni de comandos manuales para arrancar.
- Si no existe `.env`, la app lo crea automaticamente a partir de `.env.example`.
- Si el entorno incluye interfaz nativa, la app mostrara una ventana de control.
- Si no, arrancara en modo compatible y abrira la interfaz web local igualmente.

El ejecutable portable usa estas rutas por defecto:

- `..\dds`
- `..\14 RDIs`
- `..\3 BDE (PM card's)`
- `..\mid-range`

Si necesitas otra distribucion de carpetas, puedes ajustar:

- `MCM5_WORKSPACE_DIR`
- `MCM5_DDS_DIR`
- `MCM5_RDI_DIR`
- `MCM5_PM_DIR`
- `MCM5_MIE_DIR`

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

## Notas

- Si dejas `LLM_PROVIDER=auto`, la aplicacion usara la primera API disponible.
- Tambien puedes elegir el proveedor desde la web.
- Si no hay ninguna API configurada, `/consulta` responde en modo local con el contexto cargado en la base.
- La via recomendada para planta es el `.exe` portable, no el `.bat`.
