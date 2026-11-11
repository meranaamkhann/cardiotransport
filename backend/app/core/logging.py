import json
import logging
import time

from ..config import get_settings


class JsonFormatter(logging.Formatter):
    def format(self, record):
        body = {"time": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)), "level": record.levelname,
                "logger": record.name, "message": record.getMessage()}
        for key in ("method", "path", "status", "duration_ms", "user_id"):
            if hasattr(record, key):
                body[key] = getattr(record, key)
        if record.exc_info:
            body["exception"] = self.formatException(record.exc_info)
        return json.dumps(body)


def configure():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(get_settings().log_level)
