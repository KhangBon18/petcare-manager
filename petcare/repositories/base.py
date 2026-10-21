"""Small cursor helpers. Repositories never commit transactions."""


def fetch_one(connection, sql, params=()):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchone()
    finally:
        cursor.close()


def fetch_all(connection, sql, params=()):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()


def execute(connection, sql, params=()):
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params)
        return cursor.lastrowid, cursor.rowcount
    finally:
        cursor.close()


def contains_filter(search, *columns):
    """Build a parameterized substring filter, omitting it for empty search.

    Column expressions are fixed by repository code; user input is only bound
    as values. Skipping ``LIKE '%%'`` keeps ordinary catalog browsing free of
    a predicate that cannot filter rows or help the optimizer.
    """
    search = (search or "").strip()
    if not search:
        return "", ()
    pattern = f"%{search}%"
    predicate = " AND (" + " OR ".join(f"{column} LIKE %s" for column in columns) + ")"
    return predicate, (pattern,) * len(columns)
