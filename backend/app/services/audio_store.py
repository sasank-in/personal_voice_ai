import asyncio
import shutil
import uuid
from pathlib import Path


class AudioStore:
    """Private local storage. Keys are relative and never returned to clients."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def path_for(self, object_key: str) -> Path:
        return self._root / object_key

    async def save(self, user_id: uuid.UUID, audio_id: uuid.UUID, data: bytes) -> str:
        object_key = f"{user_id}/{audio_id}.wav"
        path = self.path_for(object_key)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)
        return object_key

    async def delete(self, object_key: str) -> None:
        await asyncio.to_thread(self.path_for(object_key).unlink, missing_ok=True)

    async def delete_user_files(self, user_id: uuid.UUID) -> None:
        await asyncio.to_thread(shutil.rmtree, self._root / str(user_id), ignore_errors=True)
