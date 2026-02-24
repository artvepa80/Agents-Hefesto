# Fixture: R4 — addHandler() inside a function
import logging


def setup_logging():
    logger = logging.getLogger("myapp")
    handler = logging.StreamHandler()
    logger.addHandler(handler)  # duplicated every call!
