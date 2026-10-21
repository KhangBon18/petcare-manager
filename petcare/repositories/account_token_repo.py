"""Hashed, expiring, single-use global account tokens."""

from petcare.repositories.base import execute, fetch_one


def revoke_open(connection, user_id, purpose):
    return execute(
        connection,
        "UPDATE account_tokens SET consumed_at = CURRENT_TIMESTAMP "
        "WHERE user_id = %s AND purpose = %s AND consumed_at IS NULL",
        (user_id, purpose),
    )[1]


def create(connection, user_id, purpose, token_hash, expires_minutes):
    token_id, _ = execute(
        connection,
        "INSERT INTO account_tokens (user_id, purpose, token_hash, expires_at) "
        "VALUES (%s, %s, %s, DATE_ADD(CURRENT_TIMESTAMP, INTERVAL %s MINUTE))",
        (user_id, purpose, token_hash, expires_minutes),
    )
    row = fetch_one(
        connection,
        "SELECT expires_at FROM account_tokens WHERE id = %s",
        (token_id,),
    )
    return row["expires_at"]


def user_id_for_hash(connection, token_hash, purpose):
    row = fetch_one(
        connection,
        "SELECT user_id FROM account_tokens WHERE token_hash = %s AND purpose = %s "
        "AND consumed_at IS NULL AND expires_at > CURRENT_TIMESTAMP",
        (token_hash, purpose),
    )
    return row["user_id"] if row else None


def get_open_for_update(connection, token_hash, purpose, user_id):
    return fetch_one(
        connection,
        "SELECT id, user_id, purpose FROM account_tokens WHERE token_hash = %s "
        "AND purpose = %s AND user_id = %s AND consumed_at IS NULL "
        "AND expires_at > CURRENT_TIMESTAMP FOR UPDATE",
        (token_hash, purpose, user_id),
    )


def consume(connection, token_id):
    return execute(
        connection,
        "UPDATE account_tokens SET consumed_at = CURRENT_TIMESTAMP "
        "WHERE id = %s AND consumed_at IS NULL",
        (token_id,),
    )[1]


def consume_open_for_user(connection, user_id, purpose):
    return execute(
        connection,
        "UPDATE account_tokens SET consumed_at = CURRENT_TIMESTAMP "
        "WHERE user_id = %s AND purpose = %s AND consumed_at IS NULL",
        (user_id, purpose),
    )[1]


def prune_expired(connection):
    return execute(
        connection,
        "DELETE FROM account_tokens WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL 30 DAY LIMIT 1000",
    )[1]
