from .factory import create_input_source


class InputDeviceManager:
    """Owns source lifecycle; downstream vision code sees only InputSource."""
    def __init__(self, source=None, input_type=None, **kwargs):
        self._kwargs = kwargs
        self.source = create_input_source(source=source, input_type=input_type, **kwargs)

    @property
    def status(self):
        return self.source.status

    def select(self, source=None, input_type=None, **kwargs):
        candidate = create_input_source(source=source, input_type=input_type, **{**self._kwargs, **kwargs})
        old = self.source
        self.source = candidate
        old.release()
        return self.status

    def connect(self):
        self.source.__enter__()
        return self.status

    def disconnect(self):
        self.source.release()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()
