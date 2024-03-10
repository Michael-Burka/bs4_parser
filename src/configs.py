import argparse
import logging
from logging.handlers import RotatingFileHandler
from typing import List

from constants import BASE_DIR


LOG_FORMAT = '"%(asctime)s - [%(levelname)s] - %(message)s"'
DT_FORMAT = '%d.%m.%Y %H:%M:%S'


def configure_argument_parser(
        available_modes: List[str]
) -> argparse.ArgumentParser:
    """
    Configure and returns an argument parser for managing script options,
    including operation modes, cache clearing, and output formatting.

    Args:
        available_modes (List[str]): Valid operation modes for the parser.

    Returns:
        argparse.ArgumentParser: Configured parser object.
    """
    parser = argparse.ArgumentParser(description='Python documentation parser')
    parser.add_argument(
        'mode',
        choices=available_modes,
        help='Parser operation modes'
    )
    parser.add_argument(
        '-c',
        '--clear-cache',
        action='store_true',
        help='Clear cache'
    )
    parser.add_argument(
        '-o',
        '--output',
        choices=('pretty', 'file'),
        help='Additional output methods'
    )
    return parser


def configure_logging() -> None:
    """
    Set up logging with file rotation,
    storing logs in a directory within BASE_DIR.
    Creates a rotating file handler for logging, managing file size and count.
    """
    log_dir = BASE_DIR / 'logs'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / 'parser.log'

    rotating_handler = RotatingFileHandler(
        log_file, maxBytes=10 ** 6, backupCount=5
    )
    logging.basicConfig(
        datefmt=DT_FORMAT,
        format=LOG_FORMAT,
        level=logging.INFO,
        handlers=[rotating_handler, logging.StreamHandler()]
    )
