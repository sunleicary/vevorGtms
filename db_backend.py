"""Database access layer: opt-in Neon PostgreSQL with SQLite fallback.

Set DATABASE_URL in Streamlit Secrets or the process environment.
SQL written for SQLite uses ? parameters; the adapter translates them for psycopg.
Never print the connection URL.
"""
import os
import re
import sqlite3

def database_url():
    value = os.environ.get("DATABASE_URL", "").strip()
    if value:
        return value
    try:
        import streamlit as st
        return str(st.secrets.get("DATABASE_URL", "")).strip()
    except Exception:
        return ""

def is_neon():
    return bool(database_url())

class Row(dict):
    def __init__(self, keys, values):
        super().__init__(zip(keys, values))
        self._values = tuple(values)
    def __getitem__(self, key):
        return self._values[key] if isinstance(key, int) else super().__getitem__(key)

def _row_factory(cursor):
    names = [c.name for c in cursor.description]
    def make(values):
        return Row(names, values)
    return make

def _translate(query):
    # All application queries use ? for parameters and contain no literal '?'.
    return query.replace("?", "%s")

class PgCursor:
    def __init__(self, cursor):
        self._cursor = cursor
    def execute(self, query, params=None):
        self._cursor.execute(_translate(query), params)
        return self
    def executemany(self, query, params):
        self._cursor.executemany(_translate(query), params)
        return self
    def _wrap(self, values):
        if values is None:
            return None
        names = [c.name for c in self._cursor.description]
        return Row(names, values)
    def fetchone(self):
        return self._wrap(self._cursor.fetchone())
    def fetchall(self):
        return [self._wrap(values) for values in self._cursor.fetchall()]
    @property
    def description(self):
        return self._cursor.description
    @property
    def rowcount(self):
        return self._cursor.rowcount
    def close(self):
        self._cursor.close()
    def __iter__(self):
        for values in self._cursor:
            yield self._wrap(values)
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        self.close()

class PgConnection:
    def __init__(self, conn):
        self._conn = conn
    def cursor(self):
        return PgCursor(self._conn.cursor())
    def execute(self, query, params=None):
        return self.cursor().execute(query, params)
    def executemany(self, query, params):
        return self.cursor().executemany(query, params)
    def commit(self):
        self._conn.commit()
    def rollback(self):
        self._conn.rollback()
    def close(self):
        self._conn.close()
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                self.rollback()
            else:
                self.commit()
        finally:
            self.close()

def connect(sqlite_path, timeout=30):
    url = database_url()
    if url:
        import psycopg
        return PgConnection(psycopg.connect(url, connect_timeout=15))
    conn = sqlite3.connect(sqlite_path, timeout=timeout)
    conn.row_factory = sqlite3.Row
    return conn

def read_sql(query, conn, params=None):
    import pandas as pd
    if is_neon():
        with conn.cursor() as cur:
            cur.execute(_translate(query), params)
            rows = cur.fetchall()
            columns = [c.name for c in cur.description]
        return pd.DataFrame([tuple(row[i] for i in range(len(columns))) for row in rows], columns=columns)
    return pd.read_sql_query(query, conn, params=params)
