import logging

import colorama
from tqdm import tqdm

from app.payroll_service_agent.utils.mdc_logging import MDC


colorama.init()


class TqdmLoggingHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)


class EventFormatter(logging.Formatter):
    def format(self, record):
        if isinstance(record.msg, dict) and "event" in record.msg:
            record.msg = record.msg["event"]
            record.args = ()
        mdc = MDC.get_all()
        if mdc:
            record.mdc = " ".join(f"{k}={v}" for k, v in mdc.items())
        else:
            record.mdc = ""
        return super().format(record)


class ColoredLogger(logging.Logger):
    def __init__(self, name):
        super().__init__(name)
        self.info_color = colorama.Fore.GREEN
        self.error_color = colorama.Fore.RED
        self.warning_color = colorama.Fore.YELLOW
        self.reset_color = colorama.Fore.RESET
        self.debug_color = colorama.Fore.CYAN

    def info(self, msg, *args, **kwargs):
        super().info(
            {
                "event": f"{self.info_color}{msg}{self.reset_color}",
                "logger": self.name,
                "level": "info",
            },
            *args,
            stacklevel=2,
            **kwargs,
        )

    def error(self, msg, *args, **kwargs):
        super().error(
            {
                "event": f"{self.error_color}{msg}{self.reset_color}",
                "logger": self.name,
                "level": "error",
            },
            *args,
            stacklevel=2,
            **kwargs,
        )

    def warning(self, msg, *args, **kwargs):
        super().warning(
            {
                "event": f"{self.warning_color}{msg}{self.reset_color}",
                "logger": self.name,
                "level": "warning",
            },
            *args,
            stacklevel=2,
            **kwargs,
        )

    def debug(self, msg, *args, **kwargs):
        super().debug(
            {
                "event": f"{self.debug_color}{msg}{self.reset_color}",
                "logger": self.name,
                "level": "debug",
            },
            *args,
            stacklevel=2,
            **kwargs,
        )


def setup_logger(name, log_level="INFO"):
    level_map = {"INFO": logging.INFO, "DEBUG": logging.DEBUG}
    logging_level = level_map.get(log_level.upper(), logging.INFO)

    logging.setLoggerClass(ColoredLogger)
    logger = logging.getLogger(name)
    logger.setLevel(logging_level)

    handler = TqdmLoggingHandler()
    handler.setLevel(logging_level)
    formatter = EventFormatter(
        fmt="%(asctime)s - %(filename)s:%(lineno)d - %(funcName)s() %(mdc)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)

    if not any(isinstance(h, TqdmLoggingHandler) for h in logger.handlers):
        logger.addHandler(handler)

    logger.propagate = False
    return logger
