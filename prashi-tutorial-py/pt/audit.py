from flask import g, request, session

from .db import run


def audit(action, entity, entity_id=None, summary='', user=None):
    """Records who did what. Never raises: a logging problem must not break the action itself."""
    try:
        u = user or session.get('user') or getattr(g, 'user', None) or {}
        run('INSERT INTO audit_log (user_id, user_name, action, entity, entity_id, summary, ip) VALUES (?,?,?,?,?,?,?)',
            u.get('id'), u.get('name'), action, entity, None if entity_id is None else str(entity_id),
            str(summary or '')[:500], request.remote_addr)
    except Exception as e:                                        # noqa: BLE001
        print('audit failed:', e)
