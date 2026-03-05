import logging
import sys


def setup_logging(*, log_level: str = "INFO") -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="[%(asctime)s] %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )

    noisy_loggers = ["sqlalchemy.engine", "httpcore", "googleapiclient", "httpx"]
    if level > logging.DEBUG:
        for name in noisy_loggers:
            logging.getLogger(name).setLevel(logging.WARNING)
