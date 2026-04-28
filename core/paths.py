import shutil
import sys
from pathlib import Path


DATA_DIR_NAME = "data"
DEBUG_DIR_NAME = "debug"


def _is_frozen_app():
    return bool(getattr(sys, "frozen", False) or "__compiled__" in globals())


def app_base_dir():
    if _is_frozen_app():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def resource_path(*parts):
    bundle_dir = getattr(sys, "_MEIPASS", None)
    base = Path(bundle_dir).resolve() if bundle_dir else app_base_dir()
    return str(base.joinpath(*parts))


def writable_path(*parts):
    return str(app_base_dir().joinpath(*parts))


def data_path(*parts):
    return str(app_base_dir().joinpath(DATA_DIR_NAME, *parts))


def debug_path(*parts):
    return str(app_base_dir().joinpath(DEBUG_DIR_NAME, *parts))


def ensure_writable_file(filename):
    target = Path(data_path(filename))
    source = Path(resource_path(filename))
    legacy_target = Path(writable_path(filename))
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        for candidate in (legacy_target, source):
            if not candidate.exists():
                continue
            if candidate.resolve() == target.resolve():
                break
            shutil.copy2(candidate, target)
            break
    return str(target)


def debug_output_path(filename):
    target = Path(debug_path(filename))
    target.parent.mkdir(parents=True, exist_ok=True)
    return str(target)
