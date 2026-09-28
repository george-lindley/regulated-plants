import sqlite3


class DatabaseBase:
    """
    New-schema only.

    Provides:
      - DB connection
    """

    def __init__(self, db_path: str = "weeds.db", geojson_dir=None):
        self.db_path = db_path
        self.geojson_dir = geojson_dir

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
