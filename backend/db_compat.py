import os
import re
import sqlite3 as sqlite

try:
    import psycopg
    from psycopg import errors as pg_errors
except ImportError:
    psycopg = None
    pg_errors = None


Row = sqlite.Row
IntegrityError = sqlite.IntegrityError


class HybridRow:
    def __init__(self, columns, values):
        self._columns = list(columns)
        self._values = tuple(values)
        self._index = {name: index for index, name in enumerate(self._columns)}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._values[self._index[key]]

    def __iter__(self):
        return iter(self._values)

    def keys(self):
        return self._columns

    def items(self):
        return [(column, self[column]) for column in self._columns]

    def get(self, key, default=None):
        return self[key] if key in self._index else default


def use_postgres():
    database_url = os.getenv("DATABASE_URL", "")
    return database_url.startswith("postgresql://") or database_url.startswith("postgres://")


def connect(path=None, *args, **kwargs):
    if not use_postgres():
        return sqlite.connect(path, *args, **kwargs)
    if psycopg is None:
        raise RuntimeError("psycopg is required for PostgreSQL DATABASE_URL")
    return PostgresConnection(os.getenv("DATABASE_URL"))


def translate_sql(query):
    sql = query.strip()
    sql = re.sub(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", "SERIAL PRIMARY KEY", sql, flags=re.I)
    sql = re.sub(r"\bREAL\b", "DOUBLE PRECISION", sql, flags=re.I)
    sql = sql.replace("?", "%s")

    insert_ignore = re.match(r"INSERT\s+OR\s+IGNORE\s+INTO\s+(.+)", sql, flags=re.I | re.S)
    if insert_ignore:
        sql = "INSERT INTO " + insert_ignore.group(1) + " ON CONFLICT DO NOTHING"
    return sql


class PostgresConnection:
    def __init__(self, database_url):
        self._conn = psycopg.connect(database_url)
        self.row_factory = None

    def cursor(self):
        return PostgresCursor(self)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


class PostgresCursor:
    def __init__(self, wrapper):
        self.wrapper = wrapper
        self._cursor = wrapper._conn.cursor()
        self.rowcount = -1
        self.lastrowid = None

    def execute(self, query, params=None):
        params = params or ()
        pragma = re.match(r"\s*PRAGMA\s+table_info\(([\w_]+)\)", query, flags=re.I)
        if pragma:
            table = pragma.group(1)
            self._cursor.execute(
                """
                SELECT ordinal_position - 1 AS cid,
                       column_name AS name,
                       data_type AS type,
                       CASE WHEN is_nullable = 'NO' THEN 1 ELSE 0 END AS notnull,
                       column_default AS dflt_value,
                       CASE WHEN column_name = 'id' THEN 1 ELSE 0 END AS pk
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table,),
            )
            self.rowcount = self._cursor.rowcount
            return self

        try:
            self._cursor.execute(translate_sql(query), params)
        except Exception as exc:
            if pg_errors and isinstance(exc, pg_errors.UniqueViolation):
                self.wrapper.rollback()
                raise IntegrityError(str(exc)) from exc
            raise
        self.rowcount = self._cursor.rowcount
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        return self._wrap(row) if row is not None else None

    def fetchall(self):
        return [self._wrap(row) for row in self._cursor.fetchall()]

    def _wrap(self, row):
        if self._cursor.description is None:
            return row
        columns = [item.name for item in self._cursor.description]
        return HybridRow(columns, row)
