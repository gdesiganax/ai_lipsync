
import importlib
import inspect
import pkgutil

from app.services.animation.base import AnimationEngine
from app.services.animation.registry import EngineRegistry
from app.services.animation import engines


def load_engines(config):
    registry = EngineRegistry()

    for module_info in pkgutil.iter_modules(engines.__path__):
        module = importlib.import_module(
            f"{engines.__name__}.{module_info.name}"
        )

        for _, engine_class in inspect.getmembers(
            module,
            inspect.isclass
        ):
            if (
                engine_class is AnimationEngine
                or not issubclass(engine_class, AnimationEngine)
                or inspect.isabstract(engine_class)
            ):
                continue

            engine = engine_class(config)

            registry.register(engine)

    return registry
