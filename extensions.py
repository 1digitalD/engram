from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def load_sqlite_extensions(db_instance):
    """Register sqlite-vec extension loader on every new SQLite connection."""
    from sqlalchemy import event

    @event.listens_for(db_instance.engine, "connect")
    def on_connect(dbapi_conn, connection_record):
        try:
            import sqlite_vec
            dbapi_conn.enable_load_extension(True)
            sqlite_vec.load(dbapi_conn)
            dbapi_conn.enable_load_extension(False)
        except Exception:
            # sqlite-vec not installed — vector search disabled gracefully
            pass
