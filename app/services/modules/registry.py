from app.services.modules.base import ProcessingModule


class ModuleRegistry:

    def __init__(self):
        self._modules = {}

    def register(self, module):
        if not isinstance(module, ProcessingModule):
            raise TypeError("Module must inherit from ProcessingModule.")

        if not module.module_id:
            raise ValueError("Module must define a module_id.")

        if module.module_id in self._modules:
            raise ValueError(
                f"Module already registered: {module.module_id}"
            )

        self._modules[module.module_id] = module

    def unregister(self, module_id):
        return self._modules.pop(module_id, None) is not None

    def get(self, module_id):
        return self._modules.get(module_id)

    def get_all(self):
        return [module.get_info() for module in self._modules.values()]

    def get_available(self):
        return [
            module.get_info()
            for module in self._modules.values()
            if module.is_available()
        ]

    def has(self, module_id):
        return module_id in self._modules

    def count(self):
        return len(self._modules)