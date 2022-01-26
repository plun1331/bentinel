import sys
from datetime import datetime
from typing import Callable, Dict

from .text_format import TextFormat

LogMethod = Callable[[str], None]


class Logger:

    __log_types: Dict[str, str] = {
        "info": TextFormat.blue,
        "warn": TextFormat.yellow,
        "error": TextFormat.red,
        "success": TextFormat.green,
        "emergency": TextFormat.gold,
        "notice": TextFormat.aqua,
        "critical": TextFormat.dark_red,
        "debug": TextFormat.gray
    }

    info: LogMethod
    warn: LogMethod
    error: LogMethod
    success: LogMethod
    emergency: LogMethod
    notice: LogMethod
    critical: LogMethod
    debug: LogMethod

    def __init__(self) -> None:
        if sys.platform in ["win32", "win64"]:
            from ctypes import windll

            kernel = windll.kernel32
            kernel.SetConsoleMode(kernel.GetStdHandle(-11), 7)

    def __getattr__(self, item: str) -> LogMethod:
        log_type = self.__log_types.get(item.lower())

        if not log_type:
            raise AttributeError

        return lambda content: self.__log(item, content)

    def __log(self, log_type: str, content: str) -> None:
        date_time: datetime = datetime.now()
        color: str = self.__log_types[log_type]

        print(
                f"{color}[{log_type.upper()}: "
                f"{date_time:%H:%M}]{TextFormat.white}"
                f" {content}{TextFormat.reset}"
        )