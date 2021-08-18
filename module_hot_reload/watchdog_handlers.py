from pathlib import Path
from typing import Callable, Union

from watchdog.events import (
    FileModifiedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
    FileSystemMovedEvent,
)


action = Callable[[], None]


class FileModifiedHandler(FileSystemEventHandler):
    def __init__(self, callback: action, file_path: Union[str, Path]):
        self.file_path = str(file_path)
        self.callback = callback
        super().__init__()

    def on_modified(self, event: FileModifiedEvent):
        if not event.is_directory and self.file_path == event.src_path:
            self.callback()


class DirModifiedHandler(FileSystemEventHandler):
    """
    Reacts to modifications of .py files,
    """
    def __init__(self, callback: action, dir_path: Union[str, Path]):
        self.dir_path = str(dir_path)
        self.callback = callback
        super().__init__()

    def on_modified(self, event: FileSystemEvent):
        path: str = event.src_path
        if not event.is_directory and path.endswith('.py') and '__pycache__' not in path:
            self.callback()


class NewModuleAwareDirModifiedHandler(DirModifiedHandler):
    """
    Reacts to modifications of .py files,
    creation or moving into <dir_path>(and it's children) of .py files and directories.
    __pycache__ is ignored.
    """
    def _check_and_call(self, event: FileSystemEvent):
        path: str = event.src_path
        if (event.is_directory or path.endswith('.py')) and '__pycache__' not in path:
            self.callback()

    def on_created(self, event: FileSystemEvent):
        self._check_and_call(event)

    # def on_deleted(self, event: FileSystemEvent):
    #     self._check_and_call(event)

    def on_moved(self, event: FileSystemMovedEvent):
        if self.dir_path in event.dest_path:
            self._check_and_call(event)
