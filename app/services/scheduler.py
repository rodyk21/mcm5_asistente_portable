from __future__ import annotations

import threading
import time
from datetime import datetime

from app.config import Settings
from app.database import db_session
from app.services.ingestion import process_all_sources


class NightlyIngestionScheduler:
    def __init__(self, settings: Settings, hour: int = 23, minute: int = 0) -> None:
        self.settings = settings
        self.hour = hour
        self.minute = minute
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_run_date: str | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="mcm5-nightly-ingestion", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            now = datetime.now()
            today = now.date().isoformat()
            if (
                now.hour == self.hour
                and now.minute == self.minute
                and self._last_run_date != today
            ):
                try:
                    with db_session(self.settings.db_path) as connection:
                        process_all_sources(connection, self.settings, force=False)
                    self._last_run_date = today
                except Exception:
                    pass
            time.sleep(30)
