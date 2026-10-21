"""MySQL-backed login throttling keyed by one-way hashes, not raw PII."""

from petcare.repositories.base import execute


def is_blocked(connection, key_hashes):
    if not key_hashes:
        return False
    placeholders = ",".join(["%s"] * len(key_hashes))
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT 1 FROM login_throttle WHERE key_hash IN (" + placeholders + ") "
            "AND blocked_until > NOW() LIMIT 1",
            tuple(key_hashes),
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def record_failure(connection, key_hash, threshold):
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT IGNORE INTO login_throttle "
            "(key_hash, failed_attempts, window_started_at) VALUES (%s, 0, NOW())",
            (key_hash,),
        )
        cursor.execute(
            "SELECT failed_attempts, window_started_at < NOW() - INTERVAL 15 MINUTE "
            "FROM login_throttle WHERE key_hash = %s FOR UPDATE",
            (key_hash,),
        )
        attempts, expired = cursor.fetchone()
        if expired:
            attempts = 0
            cursor.execute(
                "UPDATE login_throttle SET window_started_at = NOW(), blocked_until = NULL "
                "WHERE key_hash = %s",
                (key_hash,),
            )
        attempts += 1
        cursor.execute(
            "UPDATE login_throttle SET failed_attempts = %s, "
            "blocked_until = IF(%s >= %s, NOW() + INTERVAL 15 MINUTE, NULL), "
            "updated_at = NOW() WHERE key_hash = %s",
            (attempts, attempts, threshold, key_hash),
        )
        return attempts >= threshold
    finally:
        cursor.close()


def clear(connection, key_hashes):
    if not key_hashes:
        return
    placeholders = ",".join(["%s"] * len(key_hashes))
    execute(
        connection,
        "DELETE FROM login_throttle WHERE key_hash IN (" + placeholders + ")",
        tuple(key_hashes),
    )


def prune_old(connection):
    execute(
        connection,
        "DELETE FROM login_throttle WHERE updated_at < NOW() - INTERVAL 1 DAY LIMIT 1000",
    )
