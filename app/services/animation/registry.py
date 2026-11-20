
from app.services.animation.base import AnimationEngine


class EngineRegistry:

    def __init__(self):
        self._engines = {}

    def register(self, engine):
        if not isinstance(engine, AnimationEngine):
            raise TypeError("Engine must inherit from AnimationEngine.")

        if not engine.engine_id:
            raise ValueError("Engine must define an engine_id.")

        if engine.engine_id in self._engines:
            raise ValueError(
                f"Engine already registered: {engine.engine_id}"
            )

        self._engines[engine.engine_id] = engine

    def unregister(self, engine_id):
        return self._engines.pop(engine_id, None) is not None

    def get(self, engine_id):
        return self._engines.get(engine_id)

    def get_all(self):
        return [
            engine.get_info()
            for engine in self._engines.values()
        ]

    def get_available(self):
        return [
            engine.get_info()
            for engine in self._engines.values()
            if engine.is_available()
        ]

    def has(self, engine_id):
        return engine_id in self._engines

    def count(self):
        return len(self._engines)
