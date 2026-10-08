import copy
import logging.config
from argparse import ArgumentParser, Namespace
from types import TracebackType
from typing import Optional, Union

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
            # logging.StreamHandler defaults to sys.stderr; force stdout so
            # routine progress logging doesn't get mixed in with real errors.
            "stream": "ext://sys.stdout",
            "formatter": "brief",
            "level": "INFO",
        },
        "file": {
            "class": "logging.FileHandler",
            "formatter": "precise",
            "filename": "armoor.log",
            "level": "INFO",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "DEBUG"},
}


def setup_logging(
    console_level: Optional[str] = None, file_level: Optional[str] = None,
    to_file: Union[bool, str] = True,
    show_init_msg: bool = False, **kwargs
) -> None:
    """Setup the logging"""

    # Deep copy so dictConfig cannot mutate DEFAULT_LOGGING_CONFIG in place.
    # (dictConfig replaces each config-dict entry with the actual handler object,
    # which would permanently corrupt the global default on subsequent calls.)
    logging_config = copy.deepcopy(DEFAULT_LOGGING_CONFIG)

    # Explicitly clear root handlers before reconfiguring to prevent stale
    # handlers accumulating when setup_logging is called more than once.
    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)
        h.close()

    # Alter the config
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


def add_logging_parser_arguments(parser: ArgumentParser, default_level: str = "info") -> None:
    """Add ``--log-level``/``--log-file`` arguments to an argparse parser."""
    add_log_level_parser_arguments(parser, default_level=default_level)
    parser.add_argument(
        "--log-file", help="logging file name", default="armoor.log"
    )


def add_log_level_parser_arguments(parser: ArgumentParser, default_level: str = "info") -> None:
    """Add a ``--log-level`` argument to an argparse parser."""
    parser.add_argument(
        "--log-level",
        help="logging level",
        choices=["debug", "info", "warning", "error", "critical"],
        default=default_level,
    )

def main_setup_logging(args: Namespace) -> None:
    """Configure logging from parsed CLI args (``--log-level``/``--log-file``).

    Skips the file handler when running inside a Slurm/PBS batch job, since
    the scheduler already captures stdout/stderr to its own file.

    Parameters
    ----------
    args : argparse.Namespace
        Must carry `log_level` and `log_file` (see
        `add_logging_parser_arguments`).
    """
    import os
    # When running inside a batch job, the scheduler already captures
    # stdout/stderr to a file.  Enabling FileHandler on top would write
    # every line twice to the same file (StreamHandler→stderr + FileHandler).
    in_batch_job = bool(os.environ.get("SLURM_JOB_ID") or os.environ.get("PBS_JOBID"))
    setup_logging(
        console_level=args.log_level,
        to_file=False if in_batch_job else args.log_file,
    )


class LoggingLevelContext(object):
    """Temporarily change the logging level within a context

    Example
    -------
    >>> with LoggingLevelContext(logging.WARNING) as logger:
    >>> ... logger.warning("warning level here")
    """

    def __init__(self, level: int, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger if logger else logging.root
        self.level = level

    def __enter__(self) -> logging.Logger:
        self.old_level = self.logger.level
        self.logger.level = self.level
        return self.logger

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self.logger.level = self.old_level
