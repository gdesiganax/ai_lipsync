
class ProcessingContext:

    def __init__(self, data=None):
        self.data = data or {}
        self.results = {}
        self.metadata = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def add_result(self, module_id, result):
        self.results[module_id] = result

    def get_result(self, module_id, default=None):
        return self.results.get(module_id, default)

    def set_metadata(self, key, value):
        self.metadata[key] = value

    def get_metadata(self, key, default=None):
        return self.metadata.get(key, default)
