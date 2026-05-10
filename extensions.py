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
        except ModuleNotFoundError:
            # sqlite-vec not installed in this environment — vector search disabled gracefully
            pass
        except Exception as e:
            # sqlite-vec may fail if the shared library doesn't support extension loading
            # gracefully degrade to FTS5-only search
            import logging
            logging.getLogger(__name__).debug(f"sqlite-vec not available: {e}")
