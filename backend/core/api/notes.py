from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from common.bus import Bus
from common.db import get_session
from common.schemas import NoteCreate, NoteOut, NoteUpdate
from core.services import notes_service

from .deps import get_bus

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("", response_model=list[NoteOut])
def list_notes(q: str | None = None, tag: str | None = None, s: Session = Depends(get_session)):
    return notes_service.list_notes(s, q=q, tag=tag)


@router.post("", response_model=NoteOut, status_code=201)
async def create_note(data: NoteCreate, s: Session = Depends(get_session), bus: Bus = Depends(get_bus)):
    note = notes_service.create_note(s, data)
    s.commit()
    await bus.publish("notes", {"action": "created", "id": note.id})
    return note


@router.get("/{note_id}", response_model=NoteOut)
def get_note(note_id: int, s: Session = Depends(get_session)):
    note = notes_service.get_note(s, note_id)
    if not note:
        raise HTTPException(404, "note not found")
    return note


@router.put("/{note_id}", response_model=NoteOut)
async def update_note(note_id: int, data: NoteUpdate, s: Session = Depends(get_session), bus: Bus = Depends(get_bus)):
    note = notes_service.update_note(s, note_id, data)
    if not note:
        raise HTTPException(404, "note not found")
    s.commit()
    await bus.publish("notes", {"action": "updated", "id": note_id})
    return note


@router.delete("/{note_id}", status_code=204)
async def delete_note(note_id: int, s: Session = Depends(get_session), bus: Bus = Depends(get_bus)):
    if not notes_service.delete_note(s, note_id):
        raise HTTPException(404, "note not found")
    s.commit()
    await bus.publish("notes", {"action": "deleted", "id": note_id})
