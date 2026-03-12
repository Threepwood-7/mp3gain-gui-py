"""ctypes runtime wrapper around the vendored legacy C backend."""

from __future__ import annotations

import ctypes
import threading
from ctypes import POINTER, byref, c_char_p, c_double, c_int, c_long, c_size_t
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from .._tags.reader import TagData
from .build import backend_dll_path, build_backend

if TYPE_CHECKING:
    from pathlib import Path

TAG_FORMAT_NONE: Final[int] = 0
TAG_FORMAT_APEV2: Final[int] = 1
TAG_FORMAT_ID3: Final[int] = 2


class CBackendError(RuntimeError):
    """Raised when the C backend returns an error."""


class CBackendUnavailableError(RuntimeError):
    """Raised when the C backend cannot be loaded or built."""


class CBackendPathError(CBackendError):
    """Raised when a path cannot be encoded for the legacy C runtime."""


class _CTagInfo(ctypes.Structure):
    _fields_ = [
        ("found", c_int),
        ("tag_format", c_int),
        ("have_track_gain", c_int),
        ("have_track_peak", c_int),
        ("have_album_gain", c_int),
        ("have_album_peak", c_int),
        ("have_undo", c_int),
        ("undo_left", c_int),
        ("undo_right", c_int),
        ("undo_wrap", c_int),
        ("have_minmax_gain", c_int),
        ("min_gain", c_int),
        ("max_gain", c_int),
        ("have_album_minmax_gain", c_int),
        ("album_min_gain", c_int),
        ("album_max_gain", c_int),
        ("track_gain", c_double),
        ("track_peak", c_double),
        ("album_gain", c_double),
        ("album_peak", c_double),
    ]


@dataclass(frozen=True)
class _DllFns:
    initialize: Any
    shutdown: Any
    reset_error: Any
    get_last_error_code: Any
    get_last_error_message: Any
    analyzer_init: Any
    analyzer_reset_sample_frequency: Any
    analyzer_feed_f64: Any
    analyzer_get_title_gain: Any
    analyzer_get_album_gain: Any
    scan_file: Any
    album_scan_begin: Any
    album_scan_finish: Any
    apply_gain_file: Any
    read_tags: Any
    write_tags: Any
    delete_tags: Any


class LegacyCBackend:
    """Thread-safe access wrapper for mp3gain legacy DLL."""

    def __init__(self, *, auto_build: bool = True) -> None:
        dll_path = backend_dll_path()
        if auto_build:
            try:
                dll_path = build_backend(force=False)
            except Exception as exc:
                if not dll_path.exists():
                    raise CBackendUnavailableError(str(exc)) from exc
        if not dll_path.exists():
            raise CBackendUnavailableError(
                "C backend DLL not found. Run: python scripts/build_legacy_c_backend.py"
            )

        self._dll = ctypes.CDLL(str(dll_path))
        self._lock = threading.RLock()
        self._fns = self._bind(self._dll)
        rc = self._fns.initialize()
        if rc != 0:
            raise CBackendUnavailableError(
                self._read_last_error(default_message="initialization failed")
            )

    @staticmethod
    def _bind(dll: ctypes.CDLL) -> _DllFns:
        initialize = dll.mp3g_backend_initialize
        initialize.argtypes = []
        initialize.restype = c_int

        shutdown = dll.mp3g_backend_shutdown
        shutdown.argtypes = []
        shutdown.restype = None

        reset_error = dll.mp3g_backend_reset_error
        reset_error.argtypes = []
        reset_error.restype = None

        get_last_error_code = dll.mp3g_backend_get_last_error_code
        get_last_error_code.argtypes = []
        get_last_error_code.restype = c_int

        get_last_error_message = dll.mp3g_backend_get_last_error_message
        get_last_error_message.argtypes = [ctypes.POINTER(ctypes.c_char), c_int]
        get_last_error_message.restype = c_int

        analyzer_init = dll.mp3g_backend_analyzer_init
        analyzer_init.argtypes = [c_long]
        analyzer_init.restype = c_int

        analyzer_reset_sample_frequency = (
            dll.mp3g_backend_analyzer_reset_sample_frequency
        )
        analyzer_reset_sample_frequency.argtypes = [c_long]
        analyzer_reset_sample_frequency.restype = c_int

        analyzer_feed_f64 = dll.mp3g_backend_analyzer_feed_f64
        analyzer_feed_f64.argtypes = [
            POINTER(c_double),
            POINTER(c_double),
            c_size_t,
            c_int,
        ]
        analyzer_feed_f64.restype = c_int

        analyzer_get_title_gain = dll.mp3g_backend_analyzer_get_title_gain
        analyzer_get_title_gain.argtypes = []
        analyzer_get_title_gain.restype = c_double

        analyzer_get_album_gain = dll.mp3g_backend_analyzer_get_album_gain
        analyzer_get_album_gain.argtypes = []
        analyzer_get_album_gain.restype = c_double

        scan_file = dll.mp3g_backend_scan_file
        scan_file.argtypes = [
            c_char_p,
            c_int,
            POINTER(c_double),
            POINTER(c_double),
            POINTER(c_int),
            POINTER(c_int),
        ]
        scan_file.restype = c_int

        album_scan_begin = dll.mp3g_backend_album_scan_begin
        album_scan_begin.argtypes = []
        album_scan_begin.restype = c_int

        album_scan_finish = dll.mp3g_backend_album_scan_finish
        album_scan_finish.argtypes = [POINTER(c_double)]
        album_scan_finish.restype = c_int

        apply_gain_file = dll.mp3g_backend_apply_gain_file
        apply_gain_file.argtypes = [c_char_p, c_int, c_int, c_int, c_int, c_int]
        apply_gain_file.restype = c_int

        read_tags = dll.mp3g_backend_read_tags
        read_tags.argtypes = [c_char_p, POINTER(_CTagInfo)]
        read_tags.restype = c_int

        write_tags = dll.mp3g_backend_write_tags
        write_tags.argtypes = [c_char_p, POINTER(_CTagInfo), c_int, c_int]
        write_tags.restype = c_int

        delete_tags = dll.mp3g_backend_delete_tags
        delete_tags.argtypes = [c_char_p, c_int, c_int]
        delete_tags.restype = c_int

        return _DllFns(
            initialize=initialize,
            shutdown=shutdown,
            reset_error=reset_error,
            get_last_error_code=get_last_error_code,
            get_last_error_message=get_last_error_message,
            analyzer_init=analyzer_init,
            analyzer_reset_sample_frequency=analyzer_reset_sample_frequency,
            analyzer_feed_f64=analyzer_feed_f64,
            analyzer_get_title_gain=analyzer_get_title_gain,
            analyzer_get_album_gain=analyzer_get_album_gain,
            scan_file=scan_file,
            album_scan_begin=album_scan_begin,
            album_scan_finish=album_scan_finish,
            apply_gain_file=apply_gain_file,
            read_tags=read_tags,
            write_tags=write_tags,
            delete_tags=delete_tags,
        )

    def _read_last_error(self, *, default_message: str) -> str:
        code = self._fns.get_last_error_code()
        msg_buf = ctypes.create_string_buffer(2048)
        _ = self._fns.get_last_error_message(msg_buf, len(msg_buf))
        raw_message = msg_buf.value.decode("utf-8", errors="replace").strip()
        if raw_message:
            return f"[{code}] {raw_message}"
        return f"[{code}] {default_message}"

    @staticmethod
    def _encode_path(path: Path) -> bytes:
        try:
            return str(path).encode("mbcs")
        except UnicodeEncodeError as exc:
            raise CBackendPathError(
                f"Path cannot be encoded for legacy C runtime: {path}"
            ) from exc

    def analyze_track_gain_and_peak(self, path: Path) -> tuple[float, float]:
        gain_db, max_amp, _min_gain, _max_gain = self.scan_track_metrics(
            path, include_gain=True
        )
        return gain_db, max_amp

    def scan_track_metrics(
        self,
        path: Path,
        *,
        include_gain: bool = True,
    ) -> tuple[float, float, int, int]:
        path_bytes = self._encode_path(path)
        gain_db = c_double(0.0)
        max_amp = c_double(0.0)
        min_gain = c_int(0)
        max_gain = c_int(0)
        with self._lock:
            self._fns.reset_error()
            rc = self._fns.scan_file(
                path_bytes,
                1 if include_gain else 0,
                byref(gain_db),
                byref(max_amp),
                byref(min_gain),
                byref(max_gain),
            )
            if rc != 0:
                raise CBackendError(
                    self._read_last_error(default_message="scan file failed")
                )
        return (
            float(gain_db.value),
            float(max_amp.value),
            int(min_gain.value),
            int(max_gain.value),
        )

    def begin_album_scan(self) -> None:
        with self._lock:
            self._fns.reset_error()
            rc = self._fns.album_scan_begin()
            if rc != 0:
                raise CBackendError(
                    self._read_last_error(default_message="album scan begin failed")
                )

    def finish_album_scan(self) -> float:
        gain_db = c_double(0.0)
        with self._lock:
            self._fns.reset_error()
            rc = self._fns.album_scan_finish(byref(gain_db))
            if rc != 0:
                raise CBackendError(
                    self._read_last_error(default_message="album scan finish failed")
                )
        return float(gain_db.value)

    def apply_gain_file(
        self,
        path: Path,
        *,
        left_gain_steps: int,
        right_gain_steps: int,
        wrap_gain: bool,
        preserve_timestamp: bool,
        use_temp_file: bool,
    ) -> None:
        path_bytes = self._encode_path(path)
        with self._lock:
            self._fns.reset_error()
            rc = self._fns.apply_gain_file(
                path_bytes,
                left_gain_steps,
                right_gain_steps,
                1 if wrap_gain else 0,
                1 if preserve_timestamp else 0,
                1 if use_temp_file else 0,
            )
            if rc != 0:
                raise CBackendError(
                    self._read_last_error(default_message="apply gain failed")
                )

    @staticmethod
    def _tag_format_to_int(tag_format: str) -> int:
        if tag_format == "apev2":
            return TAG_FORMAT_APEV2
        if tag_format == "id3":
            return TAG_FORMAT_ID3
        return TAG_FORMAT_NONE

    @staticmethod
    def _int_to_tag_format(value: int) -> str:
        if value == TAG_FORMAT_APEV2:
            return "apev2"
        if value == TAG_FORMAT_ID3:
            return "id3"
        return "none"

    def read_tags(self, path: Path) -> TagData:
        path_bytes = self._encode_path(path)
        out = _CTagInfo()
        with self._lock:
            self._fns.reset_error()
            rc = self._fns.read_tags(path_bytes, ctypes.byref(out))
            if rc != 0:
                raise CBackendError(
                    self._read_last_error(default_message="read tags failed")
                )

        if out.found == 0:
            return TagData(tag_format="none")

        return TagData(
            tag_format=self._int_to_tag_format(out.tag_format),
            track_gain_db=out.track_gain if out.have_track_gain else None,
            track_peak=out.track_peak if out.have_track_peak else None,
            album_gain_db=out.album_gain if out.have_album_gain else None,
            album_peak=out.album_peak if out.have_album_peak else None,
            undo_left=out.undo_left if out.have_undo else None,
            undo_right=out.undo_right if out.have_undo else None,
            undo_mode=("W" if out.undo_wrap else "N") if out.have_undo else None,
            min_gain=out.min_gain if out.have_minmax_gain else None,
            max_gain=out.max_gain if out.have_minmax_gain else None,
            album_min_gain=out.album_min_gain if out.have_album_minmax_gain else None,
            album_max_gain=out.album_max_gain if out.have_album_minmax_gain else None,
        )

    def write_tags(
        self,
        path: Path,
        tags: TagData,
        *,
        tag_format: str,
        preserve_timestamp: bool,
    ) -> None:
        path_bytes = self._encode_path(path)
        payload = _CTagInfo()
        payload.found = 1
        payload.tag_format = self._tag_format_to_int(tag_format)
        payload.have_track_gain = 1 if tags.track_gain_db is not None else 0
        payload.have_track_peak = 1 if tags.track_peak is not None else 0
        payload.have_album_gain = 1 if tags.album_gain_db is not None else 0
        payload.have_album_peak = 1 if tags.album_peak is not None else 0
        payload.have_undo = 1 if tags.has_undo else 0
        payload.have_minmax_gain = (
            1 if (tags.min_gain is not None and tags.max_gain is not None) else 0
        )
        payload.have_album_minmax_gain = (
            1
            if (tags.album_min_gain is not None and tags.album_max_gain is not None)
            else 0
        )
        payload.track_gain = float(tags.track_gain_db or 0.0)
        payload.track_peak = float(tags.track_peak or 0.0)
        payload.album_gain = float(tags.album_gain_db or 0.0)
        payload.album_peak = float(tags.album_peak or 0.0)
        payload.undo_left = int(tags.undo_left or 0)
        payload.undo_right = int(tags.undo_right or 0)
        payload.undo_wrap = 1 if (tags.undo_mode == "W") else 0
        payload.min_gain = int(tags.min_gain or 0)
        payload.max_gain = int(tags.max_gain or 0)
        payload.album_min_gain = int(tags.album_min_gain or 0)
        payload.album_max_gain = int(tags.album_max_gain or 0)

        with self._lock:
            self._fns.reset_error()
            rc = self._fns.write_tags(
                path_bytes,
                ctypes.byref(payload),
                self._tag_format_to_int(tag_format),
                1 if preserve_timestamp else 0,
            )
            if rc != 0:
                raise CBackendError(
                    self._read_last_error(default_message="write tags failed")
                )

    def delete_tags(
        self, path: Path, *, tag_format: str | None, preserve_timestamp: bool
    ) -> None:
        path_bytes = self._encode_path(path)
        fmt = (
            TAG_FORMAT_NONE
            if tag_format is None
            else self._tag_format_to_int(tag_format)
        )
        with self._lock:
            self._fns.reset_error()
            rc = self._fns.delete_tags(path_bytes, fmt, 1 if preserve_timestamp else 0)
            if rc != 0:
                raise CBackendError(
                    self._read_last_error(default_message="delete tags failed")
                )


CBackendUnavailable = CBackendUnavailableError


_backend_lock = threading.Lock()
_backend_instance: LegacyCBackend | None = None


def get_backend(*, auto_build: bool = True) -> LegacyCBackend:
    global _backend_instance
    with _backend_lock:
        if _backend_instance is None:
            _backend_instance = LegacyCBackend(auto_build=auto_build)
        return _backend_instance
