"""Chat copilot SSE streaming endpoint router."""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.db import get_db
from app.models import Dataset
from app.schemas import ChatRequest
from app.services.copilot import run_copilot_chat

router = APIRouter(prefix="/chat", tags=["Copilot"])


@router.post("")
def chat_stream(
    req: ChatRequest,
    db: Session = Depends(get_db)
):
    """Stream copilot answers and tool invocations via Server-Sent Events (SSE)."""
    ds = db.query(Dataset).filter(Dataset.id == req.dataset_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    def event_generator():
        for item in run_copilot_chat(db=db, dataset_id=req.dataset_id, user_message=req.message):
            yield {
                "event": "message",
                "data": json.dumps(item)
            }

    return EventSourceResponse(event_generator())

