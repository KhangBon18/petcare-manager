"""Atomic MySQL request quotas shared by all application workers."""


def consume(connection, key_hash, scope, limit):
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO request_throttle "
            "(key_hash, scope, window_started_at, request_count) "
            "VALUES (%s, %s, NOW(), 1) "
            "ON DUPLICATE KEY UPDATE "
            "request_count = IF(window_started_at <= NOW() - INTERVAL 1 MINUTE, "
            "1, request_count + 1), "
            "window_started_at = IF(window_started_at <= NOW() - INTERVAL 1 MINUTE, "
            "NOW(), window_started_at), updated_at = NOW()",
            (key_hash, scope),
        )
        cursor.execute(
            "SELECT request_count, GREATEST(1, TIMESTAMPDIFF(SECOND, NOW(), "
            "window_started_at + INTERVAL 1 MINUTE)) "
            "FROM request_throttle WHERE key_hash = %s AND scope = %s",
            (key_hash, scope),
        )
        count, retry_after = cursor.fetchone()
        return count <= limit, int(retry_after)
    finally:
        cursor.close()


def prune_old(connection):
    cursor = connection.cursor()
    try:
        cursor.execute(
            "DELETE FROM request_throttle WHERE updated_at < NOW() - INTERVAL 1 DAY LIMIT 1000"
        )
        return cursor.rowcount
    finally:
        cursor.close()
