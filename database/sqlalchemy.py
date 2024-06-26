from settings import SQLITE_DB_PATH
import sqlite3 as sl

class sqlite_db:
    """
    Class for executing SQLite select queries.
    """
    def __init__(self):
        self.con = sl.connect(SQLITE_DB_PATH)

    def execute(self, query: str) -> list:
        with self.con:
            t = []
            cur = self.con.cursor()
            cur.execute(query)
            rows = cur.fetchall()
            for row in rows:
                t.append(row)
            if len(t) > 30:
                return t[:30]
            else:
                return t