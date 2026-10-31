import uuid

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.api.deps import SessionDep, StoreDep, UserDep
from app.core.errors import not_found
from app.schemas.api import DeletedAudioOut
from app.services import conversation_service

router = APIRouter(prefix="/audio", tags=["audio"])


@router.get("/{audio_id}")
async def get_audio(audio_id: uuid.UUID, user: UserDep, session: SessionDep, store: StoreDep) -> FileResponse:
    asset = await conversation_service.get_audio(session, user, audio_id)
    path = store.path_for(asset.object_key)
    if not path.exists():
        raise not_found("Audio")
    return FileResponse(path, media_type=asset.content_type, headers={"Cache-Control": "private, no-store"})


@router.delete("", response_model=DeletedAudioOut)
async def delete_all_audio(user: UserDep, session: SessionDep, store: StoreDep) -> DeletedAudioOut:
    return DeletedAudioOut(deleted=await conversation_service.delete_all_audio(session, store, user))
