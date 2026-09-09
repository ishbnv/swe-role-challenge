"""Disposable local interview configuration; contains no production credentials."""

import os

from sqlalchemy.engine import URL


def database_url() -> URL:
    return URL.create(
        "postgresql+psycopg",
        username="interview",
        password="interview_local_only",
        host="127.0.0.1",
        port=int(os.environ.get("INTERVIEW_PG_PORT", "55479")),
        database="plugin_runtime_interview",
    )
