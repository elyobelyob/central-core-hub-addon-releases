import importlib.util as _iu
import pathlib as _pl
import sys as _sys

# The add-on's modules sit two levels up. CI runs plain `pytest`, which (unlike
# `python -m pytest`) does not put the working directory on sys.path, so tests
# that `import handlers` / `import addon_updater` need it added here.
_ADDON_DIR = str(_pl.Path(__file__).resolve().parents[2])
if _ADDON_DIR not in _sys.path:
    _sys.path.insert(0, _ADDON_DIR)

# Preserve original reference
_orig_module_from_spec = getattr(_iu, "module_from_spec")


def _module_from_spec_safe(spec):
    """Wrapper that validates a ModuleSpec before delegating.

    Many test files call `importlib.util.module_from_spec(spec)` where
    `spec` may be typed as Optional[ModuleSpec]. Static analyzers (and
    some runtime checks) can complain if `None` is passed. This wrapper
    raises ImportError when `spec` is None or lacks a loader, matching
    the behavior used elsewhere in the codebase.
    """
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    return _orig_module_from_spec(spec)


# Monkeypatch the util function globally for tests
_iu.module_from_spec = _module_from_spec_safe
