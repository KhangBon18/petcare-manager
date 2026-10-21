"""Database operations for the encrypted global email delivery queue."""

from petcare.repositories.base import execute, fetch_one


def enqueue(connection, encrypted_payload, expires_at=None):
    if expires_at is not None:
        return execute(
            connection,
            "INSERT INTO email_outbox (payload_ciphertext, expires_at) VALUES (%s, %s)",
            (encrypted_payload, expires_at),
        )[0]
    return execute(
        connection,
        "INSERT INTO email_outbox (payload_ciphertext) VALUES (%s)",
        (encrypted_payload,),
    )[0]


def claim_one(connection, lease_seconds=120, message_id=None):
    sql = (
        "SELECT id, payload_ciphertext, attempt_count FROM email_outbox "
        "WHERE status IN ('pending', 'processing') AND next_attempt_at <= CURRENT_TIMESTAMP "
        "AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP) "
        "AND (locked_until IS NULL OR locked_until < CURRENT_TIMESTAMP) "
    )
    params = ()
    if message_id is not None:
        sql += "AND id = %s "
        params = (message_id,)
    sql += "ORDER BY next_attempt_at, id LIMIT 1 FOR UPDATE SKIP LOCKED"
    row = fetch_one(connection, sql, params)
    if not row:
        return None
    attempt = int(row["attempt_count"]) + 1
    execute(
        connection,
        "UPDATE email_outbox SET status = 'processing', attempt_count = %s, "
        "locked_until = DATE_ADD(CURRENT_TIMESTAMP, INTERVAL %s SECOND) WHERE id = %s",
        (attempt, lease_seconds, row["id"]),
    )
    return {**row, "attempt_count": attempt}


def mark_sent(connection, message_id):
    return execute(
        connection,
        "UPDATE email_outbox SET status = 'sent', sent_at = CURRENT_TIMESTAMP, "
        "locked_until = NULL, last_error_code = NULL WHERE id = %s AND status = 'processing'",
        (message_id,),
    )[1]


def mark_failed(connection, message_id, attempt, retry_delay_seconds, error_code, max_attempts):
    status = "failed" if attempt >= max_attempts else "pending"
    return execute(
        connection,
        "UPDATE email_outbox SET status = %s, locked_until = NULL, last_error_code = %s, "
        "next_attempt_at = DATE_ADD(CURRENT_TIMESTAMP, INTERVAL %s SECOND) "
        "WHERE id = %s AND status = 'processing'",
        (status, error_code[:64], retry_delay_seconds, message_id),
    )[1]


def prune_delivered(connection, retention_days=30):
    return execute(
        connection,
        "DELETE FROM email_outbox WHERE (status IN ('sent', 'failed') "
        "AND created_at < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL %s DAY)) "
        "OR (expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP) LIMIT 1000",
        (retention_days,),
    )[1]
