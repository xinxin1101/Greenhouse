from __future__ import annotations

import threading
import time
import webbrowser

import uvicorn

from app.config import load_config


config = load_config()


def open_browser() -> None:
    time.sleep(1.2)
    webbrowser.open(f"http://{config.host}:{config.web_port}")


if __name__ == "__main__":
    if config.open_browser:
        threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(
        "app.main:app",
        host=config.host,
        port=config.web_port,
        reload=False,
        log_level="info",
    )
