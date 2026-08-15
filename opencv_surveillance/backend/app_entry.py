# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Entry point for the packaged application.

The shell script that starts a source install can assume a terminal: somewhere
for output to go, an environment already exported, a person watching. A bundle
launched from Finder or at login has none of that, so the few things the script
did implicitly have to be done explicitly here — choose a port, put the log
somewhere findable, and make sure the port the ecosystem advertises is the port
actually listening.

Deliberately small and dependency-light. It is imported by the bundle's
launcher, which is the binary carrying the application's code identity, so
anything heavy or failure-prone belongs behind it rather than in it.
"""

import logging
import os
import socket
import sys
from pathlib import Path

DEFAULT_PORT = 8200
LOG_MAX_BYTES = 10 * 1024 * 1024


def _data_root() -> Path:
    from backend.core.paths import DATA_ROOT

    return Path(DATA_ROOT)


def _port_is_free(port: int, host: str = "0.0.0.0") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
            return True
        except OSError:
            return False


def choose_port(preferred: int = DEFAULT_PORT, attempts: int = 20) -> int:
    """
    The preferred port if it is free, otherwise the next one that is.

    A desktop application cannot fail to start because something else is already
    on its port — the user has no terminal in which to read the error, and from
    their side the app simply would not open.
    """
    for offset in range(attempts):
        candidate = preferred + offset
        if _port_is_free(candidate):
            return candidate
    return preferred


def configure_logging(data_root: Path) -> Path:
    """Send output to a file under the data root, rotating it when it grows."""
    log_dir = data_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "openeye-app.log"

    try:
        if log_path.exists() and log_path.stat().st_size > LOG_MAX_BYTES:
            log_path.replace(log_path.with_suffix(".log.1"))
    except OSError:
        pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler(sys.stderr)],
    )
    return log_path


def publish_port(port: int) -> None:
    """
    Make the chosen port the one the ecosystem advertises.

    ECOSYSTEM_SERVICE_PORT takes precedence over everything else when the client
    registers, and the registry never verifies it. So a stale or guessed value is
    published as fact, and peers quietly fail to reach a service that is running
    perfectly well on a different port. Since the port is chosen here, it is
    published here.

    An explicit setting is left alone — an operator behind a reverse proxy is
    advertising the externally reachable port on purpose, which is not something
    to overwrite.
    """
    os.environ.setdefault("OPENEYE_PORT", str(port))
    if not os.environ.get("ECOSYSTEM_SERVICE_PORT"):
        os.environ["ECOSYSTEM_SERVICE_PORT"] = str(port)


def main() -> int:
    data_root = _data_root()
    log_path = configure_logging(data_root)
    logger = logging.getLogger("openeye.launcher")

    port = choose_port(int(os.environ.get("PORT") or DEFAULT_PORT))
    publish_port(port)

    logger.info("OpenEye starting")
    logger.info("  data root: %s", data_root)
    logger.info("  log file : %s", log_path)
    logger.info("  port     : %s", port)

    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=port,
        workers=1,
        log_config=None,  # logging is configured above, for one destination
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
