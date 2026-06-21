from __future__ import annotations
import importlib
import inspect
import pkgutil
from marketbrief.core.protocols import DataSource, Section
import marketbrief.sources as sources_pkg
import marketbrief.sections as sections_pkg


def _instantiate_matching(package, protocol) -> list:
    found = []
    for mod_info in pkgutil.iter_modules(package.__path__):
        module = importlib.import_module(f"{package.__name__}.{mod_info.name}")
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ != module.__name__:
                continue  # skip imported classes, only those defined here
            instance = obj()
            if isinstance(instance, protocol):
                found.append(instance)
    return found


def discover_sources() -> list[DataSource]:
    return _instantiate_matching(sources_pkg, DataSource)


def discover_sections() -> list[Section]:
    sections = _instantiate_matching(sections_pkg, Section)
    return sorted(sections, key=lambda s: s.order)
