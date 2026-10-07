from ..models import AuditLog


def audit(db, user, action: str, entity: str, entity_id=None, **detail):
    db.add(AuditLog(user_id=getattr(user, "id", None), action=action, entity=entity, entity_id=entity_id, detail=detail))
