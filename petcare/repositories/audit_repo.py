"""Append-only operational audit events."""

import json

from petcare.repositories.base import execute, fetch_all, fetch_one


def add_event(connection, actor_user_id, event_type, entity_type, entity_id, summary, details=None):
    serialized = json.dumps(details, ensure_ascii=False, separators=(",", ":")) if details else None
    return execute(
        connection,
        "INSERT INTO audit_events "
        "(tenant_id, actor_user_id, event_type, entity_type, entity_id, summary, details) "
        "VALUES (@petcare_tenant_id, %s, %s, %s, %s, %s, %s)",
        (actor_user_id, event_type, entity_type, entity_id, summary[:255], serialized),
    )[0]


def count_events(connection):
    return fetch_one(
        connection,
        "SELECT COUNT(*) total FROM audit_events WHERE tenant_id = @petcare_tenant_id",
    )["total"]


def list_events(connection, limit=25, offset=0):
    return fetch_all(
        connection,
        "SELECT e.id, e.event_type, e.entity_type, e.entity_id, e.summary, e.details, "
        "e.created_at, u.full_name actor_name, u.username actor_username "
        "FROM audit_events e JOIN users u ON u.id = e.actor_user_id "
        "WHERE e.tenant_id = @petcare_tenant_id "
        "ORDER BY e.created_at DESC, e.id DESC LIMIT %s OFFSET %s",
        (limit, offset),
    )
