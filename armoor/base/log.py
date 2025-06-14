import logging.config

DEFAULT_LOGGING_CONFIG = {
    "version": 1,
    #    'incremental': True,
    "disable_existing_loggers": False,
    "formatters": {
        "brief": {
            "format": ("%(asctime)s %(name)-12s: %(levelname)-8s"
                       " %(message)s"),
        },
        "precise": {
            "format": "%(asctime)s %(name)-12s: %(levelname)-8s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "brief",
            "level": "INFO",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "precise",
            "filename": "armoor.log",
            "maxBytes": 1024 * 1000,
            "backupCount": 3,
            "level": "DEBUG",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "DEBUG"},
}


def setup_logging(
    console_level=None, file_level=None, to_file=True,
    show_init_msg=False, **kwargs
):
    """Setup the logging"""

    #    for handler in logging.root.handlers:
    #        logging.root.handlers.remove(handler)
    #    del logging.root.handlers[:]

    # Alter the config
    logging_config = DEFAULT_LOGGING_CONFIG.copy()
    if console_level is not None:
        logging_config["handlers"]["console"]["level"] = console_level.upper()
    if to_file is False:
        logging_config["root"]["handlers"].remove("file")
    else:
        fconfig = logging_config["handlers"]["file"]
        if isinstance(to_file, str):
            fconfig["filename"] = to_file
        if file_level is not None:
            fconfig["level"] = file_level.upper()

    # Update config
    logging_config.update(kwargs)

    # Load it
    logging.config.dictConfig(logging_config)
    if show_init_msg:
        logging.getLogger(__name__).debug(
            "*** INITIALISED LOGGING SESSION ***")


def add_logging_parser_arguments(parser, default_level="info"):
    add_log_level_parser_arguments(parser, default_level=default_level)
    parser.add_argument(
        "--log-file", help="logging file name", default="armoor.log"
    )


def add_log_level_parser_arguments(parser, default_level="info"):
    parser.add_argument(
        "--log-level",
        help="logging level",
        choices=["debug", "info", "warning", "error", "critical"],
        default=default_level,
    )


def main_setup_logging(args):
    setup_logging(
        console_level=args.log_level,
        to_file=args.log_file,
    )


class LoggingLevelContext(object):
    """Temporarily change the logging level within a context

    Example
    -------
    >>> with LoggingLevelContext(logging.WARNING) as logger:
    >>> ... logger.warning("warning level here")
    """

    def __init__(self, level, logger=None):
        self.logger = logger if logger else logging.root
        self.level = level

    def __enter__(self):
        self.old_level = self.logger.level
        self.logger.level = self.level
        return self.logger

    def __exit__(self, exc_type, exc_value, traceback):
        self.logger.level = self.old_level
