import logging
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "api_formatter": {
            "format": "[api] %(asctime)s %(levelname)s [%(funcName)s]: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "recording_formatter": {
            "format": "[recording] %(asctime)s %(levelname)s [%(funcName)s]: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "api_console": {
            "class": "logging.StreamHandler",
            "formatter": "api_formatter",
            "stream": "ext://sys.stdout",
        },
        "recording_console": {
            "class": "logging.StreamHandler",
            "formatter": "recording_formatter",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "api": {
            "handlers": ["api_console"],
            "level": "INFO",
            "propagate": False,
        },
        "recording": {
            "handlers": ["recording_console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}