import logging
import logging.config
import os

from pathlib import Path

from datetime import datetime


def setup_logging():
    """Load logging configuration"""
    timestamp = datetime.now().strftime("%Y%m%d-%H:%M:%S")

    print(f'LOG START :: {timestamp}')

    log_config_file = '../../config/log.ini'
    print(f'Using spec file :: {os.path.abspath(os.path.dirname(__file__))}/{log_config_file}')

    rootdir = os.path.abspath(os.path.dirname(__file__))
    log_config_path = os.path.join(rootdir, log_config_file)

    log_dir = "logs"
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    logging.config.fileConfig(
        log_config_path,
        disable_existing_loggers=False,
        defaults={"logfilename": f"{log_dir}/{timestamp}.log"},
    )