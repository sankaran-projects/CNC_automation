import logging
import os
from datetime import datetime

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        log_file = os.path.join(
            LOG_DIR, f"{datetime.now().strftime('%Y%m%d')}.log"
        )

        fh = logging.FileHandler(log_file)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        # Add console handler for debugging
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    return logger