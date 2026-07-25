"""Notes CRUD + search. Milestone 1 uses LIKE search; FTS5 is a later upgrade
(same API, so the swap is internal)."""
from __future__ import annotations

import json

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from common.db.models import Note
from common.schemas import NoteCreate, NoteOut, NoteUpdate


def _to_out(n: Note) -> NoteOut:
    return NoteOut(
        id=n.id,
        title=n.title,
        body=n.body,
        tags=json.loads(n.tags or "[]"),
        source=n.source,
        created_at=n.created_at,
        updated_at=n.updated_at,
    )


def list_notes(s: Session, q: str | None = None, tag: str | None = None) -> list[NoteOut]:
    stmt = select(Note).order_by(Note.updated_at.desc())
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Note.title.like(like), Note.body.like(like)))
    if tag:
        stmt = stmt.where(Note.tags.like(f'%"{tag}"%'))
    return [_to_out(n) for n in s.scalars(stmt).all()]


def get_note(s: Session, note_id: int) -> NoteOut | None:
    n = s.get(Note, note_id)
    return _to_out(n) if n else None


def create_note(s: Session, data: NoteCreate) -> NoteOut:
    title = data.title.strip()
    if not title and data.body:
        # derive a title from the first line of the body (voice notes)
        title = data.body.strip().splitlines()[0][:80]
    n = Note(
        title=title or "Untitled",
        body=data.body,
        tags=json.dumps(data.tags),
        source=data.source,
    )
    s.add(n)
    s.flush()
    return _to_out(n)


def update_note(s: Session, note_id: int, data: NoteUpdate) -> NoteOut | None:
    n = s.get(Note, note_id)
    if not n:
        return None
    if data.title is not None:
        n.title = data.title
    if data.body is not None:
        n.body = data.body
    if data.tags is not None:
        n.tags = json.dumps(data.tags)
    s.flush()
    return _to_out(n)


def delete_note(s: Session, note_id: int) -> bool:
    n = s.get(Note, note_id)
    if not n:
        return False
    s.delete(n)
    return True
