from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db.models import ModelVersion


def model_tag(card: dict) -> str:
    return f"{card['version']}-{card['trained_at'][:10]}-{card['data_source']}"


def sync(db: Session, card: dict) -> ModelVersion:
    tag = model_tag(card)
    row = db.scalar(select(ModelVersion).where(ModelVersion.tag == tag))
    if row is None:
        row = ModelVersion(tag=tag, version=card["version"], data_source=card["data_source"],
                           trained_at=datetime.fromisoformat(card["trained_at"]), card=card)
        db.add(row)
        db.flush()
    db.execute(update(ModelVersion).values(is_active=False))
    row.is_active = True
    db.commit()
    return row
