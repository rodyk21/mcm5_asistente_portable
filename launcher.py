from __future__ import annotations

import ctypes
import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen

try:
    import tkinter as tk
except ModuleNotFoundError:  # pragma: no cover - depends on Python distribution
    tk = None

import uvicorn

from app.main import app


APP_NAME = "MCM5 AI Maintenance Assistant"


def _runtime_dir() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


def _data_dir() -> Path:
    path = _runtime_dir() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _env_paths() -> tuple[Path, Path]:
    runtime_dir = _runtime_dir()
    return runtime_dir / ".env", runtime_dir / ".env.example"


def _ensure_env_file() -> Path:
    env_path, example_path = _env_paths()
    if not env_path.exists() and example_path.exists():
        shutil.copyfile(example_path, env_path)
    return env_path


def _show_error(message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, message, APP_NAME, 0x10)
    except Exception:
        pass


def _configure_logging() -> Path:
    log_path = _data_dir() / "server.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8")],
        force=True,
    )

    def _handle_exception(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            return
        logging.exception("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))
        _show_error(f"Se produjo un error inesperado.\n\nRevisa el log en:\n{log_path}")

    sys.excepthook = _handle_exception
    return log_path


def _is_our_server_running(health_url: str) -> bool:
    try:
        with urlopen(health_url, timeout=1.5) as response:
            return response.status == 200
    except Exception:
        return False


def _is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _open_with_default_app(target: Path | str) -> None:
    try:
        os.startfile(str(target))  # type: ignore[attr-defined]
    except Exception:
        if isinstance(target, Path):
            webbrowser.open(target.as_uri(), new=2)
        else:
            webbrowser.open(str(target), new=2)


def _open_browser_when_ready(ui_url: str, health_url: str) -> None:
    for _ in range(120):
        if _is_our_server_running(health_url):
            _open_with_default_app(ui_url)
            return
        time.sleep(0.5)
    logging.warning("No se pudo confirmar el arranque de la interfaz en %s", ui_url)


class DesktopLauncher:
    def __init__(self, host: str, port: int, log_path: Path) -> None:
        if tk is None:
            raise RuntimeError("tkinter no esta disponible en este entorno")
        self.host = host
        self.port = port
        self.log_path = log_path
        self.ui_url = f"http://127.0.0.1:{port}/ui"
        self.health_url = f"http://127.0.0.1:{port}/health"
        self.server: uvicorn.Server | None = None
        self.server_thread: threading.Thread | None = None
        self.auto_opened = False
        self.closing = False

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("540x320")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.configure(bg="#efe8da")

        self.status_var = tk.StringVar(value="Preparando aplicacion...")
        self.detail_var = tk.StringVar(value=f"Interfaz: {self.ui_url}")
        self.log_var = tk.StringVar(value=f"Log: {self.log_path}")

        self._build_ui()

    def _build_ui(self) -> None:
        wrap = tk.Frame(self.root, bg="#efe8da", padx=18, pady=18)
        wrap.pack(fill="both", expand=True)

        title = tk.Label(
            wrap,
            text="Asistente MCM5",
            font=("Segoe UI", 18, "bold"),
            bg="#efe8da",
            fg="#1f2b26",
        )
        title.pack(anchor="w")

        subtitle = tk.Label(
            wrap,
            text="Aplicacion local para consulta tecnica, historico e ingesta de datos.",
            font=("Segoe UI", 10),
            bg="#efe8da",
            fg="#5f6d66",
        )
        subtitle.pack(anchor="w", pady=(4, 16))

        card = tk.Frame(wrap, bg="#fffaf0", bd=1, relief="solid", padx=14, pady=14)
        card.pack(fill="x")

        tk.Label(card, textvariable=self.status_var, font=("Segoe UI", 11, "bold"), bg="#fffaf0", fg="#0c6a57").pack(
            anchor="w"
        )
        tk.Label(card, textvariable=self.detail_var, font=("Segoe UI", 10), bg="#fffaf0", fg="#1f2b26").pack(
            anchor="w", pady=(6, 2)
        )
        tk.Label(card, textvariable=self.log_var, font=("Segoe UI", 9), bg="#fffaf0", fg="#5f6d66").pack(anchor="w")

        button_row = tk.Frame(wrap, bg="#efe8da")
        button_row.pack(fill="x", pady=(18, 10))

        self.open_button = tk.Button(
            button_row,
            text="Abrir interfaz",
            command=self.open_ui,
            bg="#0c6a57",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=8,
            relief="flat",
        )
        self.open_button.pack(side="left", padx=(0, 8))

        self.env_button = tk.Button(
            button_row,
            text="Configurar APIs",
            command=self.open_env,
            bg="#bf642c",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=8,
            relief="flat",
        )
        self.env_button.pack(side="left", padx=(0, 8))

        self.data_button = tk.Button(
            button_row,
            text="Abrir datos",
            command=self.open_data_dir,
            bg="#ffffff",
            fg="#1f2b26",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=8,
            relief="solid",
            bd=1,
        )
        self.data_button.pack(side="left")

        footer_row = tk.Frame(wrap, bg="#efe8da")
        footer_row.pack(fill="x", side="bottom", pady=(18, 0))

        self.close_button = tk.Button(
            footer_row,
            text="Cerrar aplicacion",
            command=self.close,
            bg="#ffffff",
            fg="#1f2b26",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=8,
            relief="solid",
            bd=1,
        )
        self.close_button.pack(side="right")

    def start(self) -> int:
        self._ensure_server()
        self.root.after(400, self._poll_server_ready)
        self.root.mainloop()
        return 0

    def _ensure_server(self) -> None:
        if _is_our_server_running(self.health_url):
            self.status_var.set("La aplicacion ya estaba abierta")
            self.detail_var.set(f"Interfaz disponible en {self.ui_url}")
            self.auto_opened = True
            self.open_ui()
            return

        config = uvicorn.Config(app, host=self.host, port=self.port, access_log=False, log_level="info")
        self.server = uvicorn.Server(config)
        self.server_thread = threading.Thread(target=self.server.run, daemon=True, name="mcm5-server")
        self.server_thread.start()
        self.status_var.set("Arrancando servidor local...")
        self.detail_var.set("Espera unos segundos mientras la interfaz queda lista.")

    def _poll_server_ready(self) -> None:
        if self.closing:
            return
        if _is_our_server_running(self.health_url):
            self.status_var.set("Aplicacion lista")
            self.detail_var.set(f"Interfaz disponible en {self.ui_url}")
            if not self.auto_opened:
                self.auto_opened = True
                self.open_ui()
            return
        self.root.after(600, self._poll_server_ready)

    def open_ui(self) -> None:
        _open_with_default_app(self.ui_url)

    def open_env(self) -> None:
        env_path = _ensure_env_file()
        try:
            subprocess.Popen(["notepad.exe", str(env_path)])
        except Exception:
            _open_with_default_app(env_path)

    def open_data_dir(self) -> None:
        _open_with_default_app(_data_dir())

    def close(self) -> None:
        if self.closing:
            return
        self.closing = True
        self.status_var.set("Cerrando aplicacion...")
        self.open_button.configure(state="disabled")
        self.env_button.configure(state="disabled")
        self.data_button.configure(state="disabled")
        self.close_button.configure(state="disabled")

        if self.server:
            self.server.should_exit = True
        self.root.after(100, self._finish_close)

    def _finish_close(self) -> None:
        if self.server_thread and self.server_thread.is_alive():
            self.root.after(100, self._finish_close)
            return
        self.root.destroy()


def main() -> int:
    log_path = _configure_logging()
    _ensure_env_file()

    host = os.getenv("MCM5_HOST", "127.0.0.1")
    port = int(os.getenv("MCM5_PORT", "8080"))
    ui_url = f"http://127.0.0.1:{port}/ui"
    health_url = f"http://127.0.0.1:{port}/health"

    if _is_our_server_running(health_url):
        logging.info("La aplicacion ya estaba en ejecucion. Abriendo interfaz.")
        _open_with_default_app(ui_url)
        return 0

    if _is_port_in_use(port):
        message = (
            f"El puerto {port} ya esta en uso y no parece ser esta aplicacion.\n\n"
            "Cierra el proceso que lo usa o cambia MCM5_PORT en el archivo .env."
        )
        logging.error(message)
        _show_error(message)
        return 1

    if tk is None:
        logging.warning("tkinter no esta disponible. Se usara el modo compatible sin ventana nativa.")
        threading.Thread(
            target=_open_browser_when_ready,
            args=(ui_url, health_url),
            daemon=True,
            name="open-browser",
        ).start()
        logging.info("Iniciando servidor en %s:%s", host, port)
        uvicorn.run(app, host=host, port=port, access_log=False, log_level="info")
        return 0

    launcher = DesktopLauncher(host=host, port=port, log_path=log_path)
    return launcher.start()


if __name__ == "__main__":
    raise SystemExit(main())
