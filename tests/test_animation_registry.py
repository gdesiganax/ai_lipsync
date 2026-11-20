
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.animation.base import AnimationEngine
from app.services.animation.registry import EngineRegistry


class FakeEngine(AnimationEngine):
    engine_id = "fake_engine"
    name = "Fake Engine"
    description = "Registry test engine."

    def is_available(self):
        return True

    def generate(
        self,
        image_path,
        audio_path,
        output_dir,
        options=None,
        progress_callback=None,
    ):
        return {"success": True}


def test_registry():
    registry = EngineRegistry()

    engine = FakeEngine()

    registry.register(engine)

    assert registry.count() == 1
    assert registry.has("fake_engine")
    assert registry.get("fake_engine") is engine
    assert len(registry.get_all()) == 1
    assert len(registry.get_available()) == 1

    assert registry.unregister("fake_engine") is True
    assert registry.count() == 0
    assert registry.has("fake_engine") is False

    print("SUCCESS: Engine registry tests passed.")


if __name__ == "__main__":
    test_registry()
