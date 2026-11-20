from abc import ABC, abstractmethod


class AnimationEngine(ABC):
    engine_id = None
    name = None
    description = None

    version = "1.0"
    task_type = "image_to_video"
    capabilities = []

    requirements = {
        "gpu": False,
        "minimum_vram_gb": 0,
    }

    options = []

    @abstractmethod
    def is_available(self):
        pass

    @abstractmethod
    def generate(
        self,
        image_path,
        audio_path,
        output_dir,
        options=None,
        progress_callback=None,
    ):
        pass

    def get_info(self):
        return {
            "id": self.engine_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "task_type": self.task_type,
            "capabilities": self.capabilities,
            "requirements": self.requirements,
            "options": self.options,
            "available": self.is_available(),
        }