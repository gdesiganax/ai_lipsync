from abc import ABC, abstractmethod


class ProcessingModule(ABC):
    module_id = None
    name = None
    description = None

    version = "1.0"
    category = "general"

    requirements = {
        "gpu": False,
        "minimum_vram_gb": 0,
    }

    options = []

    @abstractmethod
    def is_available(self):
        pass

    @abstractmethod
    def process(self, input_data, options=None, progress_callback=None):
        pass

    def get_info(self):
        return {
            "id": self.module_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "category": self.category,
            "requirements": self.requirements,
            "options": self.options,
            "available": self.is_available(),
        }