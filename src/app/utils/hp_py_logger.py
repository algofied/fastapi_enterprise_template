# src/app/utils/hp_py_logger.py
"""
Industry-grade logging for FastAPI:
- Context bound at record-creation time via a LogRecord factory (request_id, user, method, path, ip)
- Non-blocking QueueHandler/QueueListener pipeline
- Sinks: stdout, files (rotating or watched), Loki push, relational DB, MinIO batch
- Timezone-aware timestamps
- No handler-thread context overwrites

Usage:
    from app.core.config import get_settings
    from app.utils.hp_py_logger import init_logging, hp_log
    settings = get_settings()
    hp_log = init_logging(settings=settings)  # call once before app creation
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import queue
import socket
import threading
import time
from datetime import datetime, timezone
from logging.handlers import (
    QueueHandler,
    QueueListener,
    RotatingFileHandler,
    WatchedFileHandler,
)
from typing import Any, Dict, List, Optional, Sequence

# ---------- contextvars ----------
import contextvars

_REQUEST_CTX: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    "request_ctx", default={}
)

CONTEXT_KEYS = ("request_id", "user", "method", "path", "ip")


def set_request_context(**kwargs) -> None:
    """
    Merge key/value pairs into the current request context.
    Call this in middleware (request_id/method/path/ip) and once the user is known.
    """
    ctx = {**_REQUEST_CTX.get(), **kwargs}
    _REQUEST_CTX.set(ctx)


def update_request_context(**kwargs) -> None:
    set_request_context(**kwargs)


def clear_request_context() -> None:
    _REQUEST_CTX.set({})


# ---------- LogRecord factory (binds context in the request thread) ----------
def _install_record_factory() -> None:
    """
    Replace the default LogRecord factory so that every record produced in the
    REQUEST THREAD has request context fields already attached.

    This makes logs safe when using QueueHandler/QueueListener because the
    final handlers run in a different thread and won't re-read contextvars.
    """
    old_factory = logging.getLogRecordFactory()

    def factory(*args, **kwargs) -> logging.LogRecord:
        record = old_factory(*args, **kwargs)

        # copy request context (snapshot) into record
        ctx = _REQUEST_CTX.get() or {}
        for key in CONTEXT_KEYS:
            val = ctx.get(key)
            if val is not None:
                setattr(record, key, val)
            else:
                # ensure attribute exists for formatters
                setattr(record, key, getattr(record, key, None))

        # stable attributes
        if not hasattr(record, "env"):
            record.env = os.getenv("ENVIRONMENT", "dev")
        if not hasattr(record, "service"):
            record.service = os.getenv("SERVICE_NAME", "app")
        if not hasattr(record, "host"):
            record.host = socket.gethostname()

        return record

    logging.setLogRecordFactory(factory)


# ---------- formatting ----------
class JSONFormatter(logging.Formatter):
    def __init__(self, tz: datetime.tzinfo | None = None):
        super().__init__()
        self.tz = tz or timezone.utc

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=self.tz).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "fn": record.funcName,
            "line": record.lineno,
            "process": record.process,
            "thread": record.thread,
            # request context
            "request_id": getattr(record, "request_id", None),
            "user": getattr(record, "user", None),
            "method": getattr(record, "method", None),
            "path": getattr(record, "path", None),
            "ip": getattr(record, "ip", None),
            "env": getattr(record, "env", None),
            "service": getattr(record, "service", None),
            "host": getattr(record, "host", None),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class PlainFormatter(logging.Formatter):
    default_fmt = (
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s "
        "| req=%(request_id)s user=%(user)s %(method)s %(path)s ip=%(ip)s"
    )

    def __init__(self, tz: datetime.tzinfo | None = None, fmt: Optional[str] = None):
        super().__init__(fmt or self.default_fmt)
        self.tz = tz or timezone.utc


# ---------- utility filters ----------
class BelowWarningFilter(logging.Filter):
    """Allow only DEBUG and INFO to pass (e.g., to access.log)."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < logging.WARNING


class ExcludePathsFilter(logging.Filter):
    """Drop request lines for matched paths (e.g., /health,/metrics)."""

    def __init__(self, patterns: Sequence[str]):
        super().__init__()
        self._patterns = [p for p in patterns if p]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        path = getattr(record, "path", None)
        has = lambda s: (s in msg) or (path and s in path)
        return not any(has(p) for p in self._patterns)


# ---------- optional sinks ----------
class LokiHTTPHandler(logging.Handler):
    """
    Send logs directly to Loki /loki/api/v1/push.
    In Kubernetes, prefer stdout + Promtail scraping. This direct push
    is provided for environments without an agent.
    """

    def __init__(self, url: str, labels: str, timeout_s: int = 3, level=logging.INFO):
        super().__init__(level=level)
        self.url = url
        self.labels = self._parse_labels(labels)
        self.timeout_s = timeout_s
        try:
            import requests  # noqa
            self._requests = requests
        except Exception as e:
            raise RuntimeError("requests is required for LokiHTTPHandler") from e

    def _parse_labels(self, labels: str) -> Dict[str, str]:
        lab: Dict[str, str] = {}
        for pair in labels.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                lab[k.strip()] = v.strip()
        if "host" not in lab:
            lab["host"] = socket.gethostname()
        return lab

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
            ts_ns = str(int(record.created * 1e9))  # Loki expects ns epoch
            streams = [{"stream": self.labels, "values": [[ts_ns, line]]}]
            resp = self._requests.post(
                self.url, json={"streams": streams}, timeout=self.timeout_s
            )
            if resp.status_code >= 400:
                # drop silently in logging path
                pass
        except Exception:
            pass


class DBHandler(logging.Handler):
    """
    Insert log lines into a relational DB table.
    Use only when required; otherwise ship JSON logs to ELK/Loki.
    """

    DDL = """
    CREATE TABLE IF NOT EXISTS {table} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        level TEXT NOT NULL,
        logger TEXT NOT NULL,
        message TEXT NOT NULL,
        request_id TEXT,
        user TEXT,
        method TEXT,
        path TEXT,
        ip TEXT,
        env TEXT,
        service TEXT,
        host TEXT
    )
    """

    def __init__(self, url: str, table: str = "app_logs", level=logging.INFO):
        super().__init__(level=level)
        try:
            from sqlalchemy import create_engine, text
            self._create_engine = create_engine
            self._text = text
        except Exception as e:
            raise RuntimeError("SQLAlchemy is required for DBHandler") from e
        self.url = url
        self.table = table
        self.engine = self._create_engine(self.url)
        with self.engine.begin() as conn:
            conn.execute(self._text(self.DDL.format(table=self.table)))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload = {
                "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "request_id": getattr(record, "request_id", None),
                "user": getattr(record, "user", None),
                "method": getattr(record, "method", None),
                "path": getattr(record, "path", None),
                "ip": getattr(record, "ip", None),
                "env": getattr(record, "env", None),
                "service": getattr(record, "service", None),
                "host": getattr(record, "host", None),
            }
            cols = ",".join(payload.keys())
            vals = ",".join([f":{k}" for k in payload.keys()])
            sql = f"INSERT INTO {self.table} ({cols}) VALUES ({vals})"
            with self.engine.begin() as conn:
                conn.execute(self._text(sql), payload)
        except Exception:
            pass


class MinioBatchHandler(logging.Handler):
    """
    Buffer JSONL lines in memory and periodically flush as an object to MinIO.
    Object key: logs/{service}/{YYYY}/{MM}/{DD}/{HH}/batch-{pid}-{seq}.jsonl
    """

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
        flush_lines: int = 100,
        flush_secs: int = 5,
        level=logging.INFO,
    ):
        super().__init__(level=level)
        try:
            from minio import Minio
        except Exception as e:
            raise RuntimeError("minio is required for MinioBatchHandler") from e

        self.client = Minio(
            endpoint, access_key=access_key, secret_key=secret_key, secure=secure
        )
        self.bucket = bucket
        self.flush_lines = flush_lines
        self.flush_secs = flush_secs
        self._buf: List[str] = []
        self._last_flush = time.time()
        self._seq = 0
        self._service = os.getenv("SERVICE_NAME", "app")
        self._pid = os.getpid()
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except Exception:
            pass
        self._lock = threading.Lock()

    def _object_key(self) -> str:
        now = datetime.utcnow()
        return f"logs/{self._service}/{now:%Y/%m/%d/%H}/batch-{self._pid}-{self._seq}.jsonl"

    def _should_flush(self) -> bool:
        return len(self._buf) >= self.flush_lines or (time.time() - self._last_flush) >= self.flush_secs

    def _flush_locked(self):
        if not self._buf:
            return
        data = ("\n".join(self._buf) + "\n").encode("utf-8")
        key = self._object_key()
        try:
            from io import BytesIO
            self.client.put_object(
                self.bucket, key, BytesIO(data), length=len(data), content_type="application/json"
            )
            self._seq += 1
            self._buf.clear()
            self._last_flush = time.time()
        except Exception:
            self._buf.clear()
            self._last_flush = time.time()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
            with self._lock:
                self._buf.append(line)
                if self._should_flush():
                    self._flush_locked()
        except Exception:
            pass

    def close(self) -> None:
        try:
            with self._lock:
                self._flush_locked()
        finally:
            super().close()


# ---------- builder ----------
hp_log = logging.getLogger("app")


class _ListenerBundle:
    def __init__(self, listener: QueueListener, handlers: List[logging.Handler]):
        self.listener = listener
        self.handlers = handlers


_listener_bundle: Optional[_ListenerBundle] = None


def init_logging(
    *,
    settings=None,
    service: Optional[str] = None,  # backward-compat
    env_file: Optional[str] = None,  # backward-compat
) -> logging.Logger:
    """
    Initialize the logging system ONCE.
    Prefer passing a Settings object (from app.core.config).
    """
    global _listener_bundle

    if getattr(logging, "_hp_logger_installed", False):
        return hp_log

    # record factory first
    _install_record_factory()

    # Load from settings (preferred) or env shim
    if settings is None:
        class _Shim:
            service_name = service or os.getenv("SERVICE_NAME", "app")
            environment = os.getenv("ENVIRONMENT", "dev")
            log_format = os.getenv("LOG_FORMAT", "json")
            log_to_stdout = os.getenv("LOG_TO_STDOUT", "true").lower() == "true"
            log_to_file = os.getenv("LOG_TO_FILE", "false").lower() == "true"
            log_level = os.getenv("LOG_LEVEL", "INFO")
            log_exclude_paths = os.getenv("LOG_EXCLUDE_PATHS", "")
            log_dir = os.getenv("LOG_DIR", f"/var/log/{service or 'app'}")
            access_log_file = os.getenv("ACCESS_LOG_FILE", "access.log")
            error_log_file = os.getenv("ERROR_LOG_FILE", "error.log")
            log_file_strategy = os.getenv("LOG_FILE_STRATEGY", "rotating")
            log_max_mb = int(os.getenv("LOG_MAX_MB", "50"))
            log_backups = int(os.getenv("LOG_BACKUPS", "10"))
            logs_timezone = os.getenv("LOGS_TIMEZONE") or os.getenv("TIMEZONE") or "UTC"
            loki_enable = os.getenv("LOKI_ENABLE", "false").lower() == "true"
            loki_url = os.getenv("LOKI_URL")
            loki_labels = os.getenv("LOKI_LABELS", f"job={(service or 'app')}")
            loki_timeout_s = int(os.getenv("LOKI_TIMEOUT_S", "3"))
            log_db_enable = os.getenv("LOG_DB_ENABLE", "false").lower() == "true"
            log_db_url = os.getenv("LOG_DB_URL")
            log_db_table = os.getenv("LOG_DB_TABLE", "app_logs")
            minio_enable = os.getenv("MINIO_ENABLE", "false").lower() == "true"
            minio_endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
            minio_secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
            minio_access_key = os.getenv("MINIO_ACCESS_KEY", "minio")
            minio_secret_key = os.getenv("MINIO_SECRET_KEY", "minio123")
            minio_bucket = os.getenv("MINIO_BUCKET", "service-logs")
            minio_flush_lines = int(os.getenv("MINIO_FLUSH_LINES", "100"))
            minio_flush_secs = int(os.getenv("MINIO_FLUSH_SECS", "5"))

            def logging_defaults(self):
                return {
                    "service": self.service_name,
                    "environment": self.environment,
                    "format": self.log_format,
                    "to_stdout": self.log_to_stdout,
                    "to_file": self.log_to_file,
                    "level": self.log_level,
                    "exclude_paths": [p.strip() for p in self.log_exclude_paths.split(",") if p.strip()],
                    "file_strategy": self.log_file_strategy,
                    "max_mb": self.log_max_mb,
                    "backups": self.log_backups,
                    "logs_timezone": self.logs_timezone,
                }

        settings = _Shim()

    defaults = settings.logging_defaults()

    # timezone
    tz_name = (
        getattr(settings, "logs_timezone", None)
        or defaults.get("logs_timezone")
        or getattr(settings, "timezone", None)
        or os.getenv("LOGS_TIMEZONE")
        or os.getenv("TIMEZONE")
        or "UTC"
    )
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc

    root_level = getattr(logging, defaults["level"].upper(), logging.INFO)
    fmt = defaults["format"]
    to_stdout = defaults["to_stdout"]
    to_file = defaults["to_file"]

    # formatters
    json_fmt = JSONFormatter(tz=tz)
    plain_fmt = PlainFormatter(tz=tz)

    # basic filters
    below_warn = BelowWarningFilter()
    exclude = ExcludePathsFilter(defaults["exclude_paths"])

    # sinks (consumer side) - NO context filters here
    handlers: List[logging.Handler] = []

    if to_stdout:
        h = logging.StreamHandler()
        h.setLevel(root_level)
        h.setFormatter(json_fmt if fmt == "json" else plain_fmt)
        handlers.append(h)

    if to_file:
        os.makedirs(settings.log_dir, exist_ok=True)
        if settings.log_file_strategy == "watched":
            access_file = WatchedFileHandler(os.path.join(settings.log_dir, settings.access_log_file))
            error_file = WatchedFileHandler(os.path.join(settings.log_dir, settings.error_log_file))
        else:
            access_file = RotatingFileHandler(
                os.path.join(settings.log_dir, settings.access_log_file),
                maxBytes=settings.log_max_mb * 1024 * 1024,
                backupCount=settings.log_backups,
            )
            error_file = RotatingFileHandler(
                os.path.join(settings.log_dir, settings.error_log_file),
                maxBytes=settings.log_max_mb * 1024 * 1024,
                backupCount=settings.log_backups,
            )

        # access: only below WARNING, and exclude certain paths
        access_file.setLevel(root_level)
        access_file.addFilter(below_warn)
        access_file.addFilter(exclude)
        access_file.setFormatter(json_fmt if fmt == "json" else plain_fmt)
        handlers.append(access_file)

        # error: WARNING and above
        error_file.setLevel(logging.WARNING)
        error_file.setFormatter(json_fmt if fmt == "json" else plain_fmt)
        handlers.append(error_file)

    # Loki (optional)
    if getattr(settings, "loki_enable", False) and getattr(settings, "loki_url", None):
        try:
            loki = LokiHTTPHandler(
                settings.loki_url, getattr(settings, "loki_labels", "job=app"), timeout_s=getattr(settings, "loki_timeout_s", 3)
            )
            loki.setLevel(root_level)
            loki.setFormatter(json_fmt)  # Loki benefits from JSON
            handlers.append(loki)
        except Exception:
            pass

    # DB sink (optional)
    if getattr(settings, "log_db_enable", False) and getattr(settings, "log_db_url", None):
        try:
            dbh = DBHandler(settings.log_db_url, table=settings.log_db_table)
            dbh.setLevel(root_level)
            dbh.setFormatter(json_fmt)
            handlers.append(dbh)
        except Exception:
            pass

    # MinIO sink (optional)
    if getattr(settings, "minio_enable", False):
        try:
            mh = MinioBatchHandler(
                endpoint=settings.minio_endpoint,
                access_key=getattr(settings, "minio_access_key", None),
                secret_key=getattr(settings, "minio_secret_key", None),
                bucket=settings.minio_bucket,
                secure=getattr(settings, "minio_secure", False),
                flush_lines=getattr(settings, "minio_flush_lines", 100),
                flush_secs=getattr(settings, "minio_flush_secs", 5),
            )
            mh.setLevel(root_level)
            mh.setFormatter(json_fmt)  # upload JSON lines
            handlers.append(mh)
        except Exception:
            pass

    # Build the queue pipeline
    log_queue: queue.Queue = queue.Queue(-1)
    qh = QueueHandler(log_queue)
    qh.setLevel(root_level)

    root = logging.getLogger()
    root.handlers = []
    root.addHandler(qh)
    root.setLevel(root_level)

    listener = QueueListener(log_queue, *handlers, respect_handler_level=True)
    listener.start()

    _listener_bundle = _ListenerBundle(listener, handlers)
    atexit.register(_shutdown_logging)

    # Let third-party loggers propagate to root; control their levels if desired
    for noisy in ("uvicorn.error", "uvicorn.access", "hypercorn.error", "hypercorn.access", "sqlalchemy.pool"):
        lg = logging.getLogger(noisy)
        lg.propagate = True
        lg.handlers = []
        # keep defaults; you can adjust:
        # lg.setLevel(logging.WARNING)

    logging._hp_logger_installed = True  # type: ignore[attr-defined]
    return logging.getLogger("app")


def _shutdown_logging():
    global _listener_bundle
    try:
        if _listener_bundle is not None:
            _listener_bundle.listener.stop()
            for h in _listener_bundle.handlers:
                try:
                    h.close()
                except Exception:
                    pass
    finally:
        _listener_bundle = None
