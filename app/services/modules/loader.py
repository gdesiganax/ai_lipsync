import importlib
import inspect
import pkgutil

from app.services.modules.base import ProcessingModule
from app.services.modules.registry import ModuleRegistry
from app.services.modules import processors


def load_modules(config):
    registry = ModuleRegistry()

    for module_info in pkgutil.iter_modules(processors.__path__):
        module = importlib.import_module(
            f"{processors.__name__}.{module_info.name}"
        )

        for _, module_class in inspect.getmembers(
            module, inspect.isclass
        ):
            if (
                module_class is ProcessingModule
                or not issubclass(module_class, ProcessingModule)
                or inspect.isabstract(module_class)
            ):
                continue

            processing_module = module_class(config)
            registry.register(processing_module)

    return registry