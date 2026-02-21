"""
Centralized logging configuration for the GCP Document AI showcase.
"""

import logging
import os
from typing import Optional


def setup_logging(level: Optional[str] = None) -> None:
    """
    Set up logging configuration for the entire application.

    Args:
        level: Optional logging level override (DEBUG, INFO, WARNING, ERROR)
    """
    if level:
        log_level = getattr(logging, level.upper(), logging.INFO)
    else:
        env_level = os.getenv('GCP_DOCAI_LOG_LEVEL', 'INFO').upper()
        log_level = getattr(logging, env_level, logging.INFO)

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(funcName)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        force=True
    )

    loggers = {
        'gcp_docai_client': log_level,
        'app': log_level,
        'urllib3': logging.WARNING,
        'requests': logging.WARNING,
        'streamlit': logging.WARNING,
    }

    for logger_name, logger_level in loggers.items():
        logging.getLogger(logger_name).setLevel(logger_level)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with consistent formatting.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
