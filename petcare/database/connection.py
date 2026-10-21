"""MySQL connection and transaction helpers."""

from contextlib import contextmanager
from hashlib import sha256
from threading import Lock

import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool

from petcare.config import Config, migration_mysql_config, mysql_config


_POOL_LOCK = Lock()
_RUNTIME_POOLS = {}


def _runtime_pool():
    config = mysql_config()
    pool_size = int(Config.DB_POOL_SIZE)
    if not 1 <= pool_size <= 32:
        raise RuntimeError("DB_POOL_SIZE must be between 1 and 32 connections per process.")
    # Include credentials in the cache key without keeping a reversible secret
    # in the pool name. A credential/database change creates a fresh pool.
    # Include TLS settings as well as credentials so CA rotation cannot keep
    # handing out connections from a pool created with an older trust bundle.
    fingerprint = sha256(repr((tuple(sorted(config.items())), pool_size)).encode("utf-8")).hexdigest()
    pool_name = "petcare_" + fingerprint[:24]
    with _POOL_LOCK:
        pool = _RUNTIME_POOLS.get(fingerprint)
        if pool is None:
            pool = MySQLConnectionPool(
                pool_name=pool_name,
                pool_size=pool_size,
                pool_reset_session=True,
                **config,
            )
            _RUNTIME_POOLS[fingerprint] = pool
        return pool


def _initialize_session(connection):
    cursor = connection.cursor()
    try:
        cursor.execute("SET time_zone = '+00:00'")
        cursor.execute("SET @petcare_tenant_id = NULL")
    except Exception:
        connection.close()
        raise
    finally:
        cursor.close()
    return connection


def get_connection():
    return _initialize_session(_runtime_pool().get_connection())


def get_migration_connection():
    return _initialize_session(mysql.connector.connect(**migration_mysql_config()))


@contextmanager
def read_connection():
    connection = get_connection()
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def transaction():
    """Commit on success and rollback any failed operation."""
    connection = get_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@contextmanager
def migration_transaction():
    """Commit one-off DDL/backfill work using the separate migration account."""
    connection = get_migration_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
