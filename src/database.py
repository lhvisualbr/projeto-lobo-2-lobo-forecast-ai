"""
database.py
Criação e carga do banco SQLite a partir dos CSVs validados em data/raw/.

O banco é sempre recriado do zero: nada aqui depende de estado anterior.
"""

import sqlite3

import pandas as pd

from config import DATA_RAW_DIR, DATABASE_DIR, DATABASE_PATH, SQL_DIR


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    schema_sql = (SQL_DIR / "schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    conn.commit()


def load_data(conn: sqlite3.Connection) -> None:
    products = pd.read_csv(DATA_RAW_DIR / "products.csv")
    calendar = pd.read_csv(DATA_RAW_DIR / "calendar.csv")
    consumption = pd.read_csv(DATA_RAW_DIR / "consumption.csv")
    inventory = pd.read_csv(DATA_RAW_DIR / "inventory_snapshot.csv")

    # is_known vem como True/False do pandas; SQLite espera 0/1.
    calendar["is_known"] = calendar["is_known"].astype(int)

    products.to_sql("products", conn, if_exists="append", index=False)
    calendar.to_sql("calendar", conn, if_exists="append", index=False)
    consumption.to_sql("consumption", conn, if_exists="append", index=False)
    inventory.to_sql("inventory_snapshot", conn, if_exists="append", index=False)
    conn.commit()


def rebuild_database() -> None:
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    conn = get_connection()
    try:
        create_schema(conn)
        load_data(conn)

        counts = {}
        for table in ["products", "calendar", "consumption", "inventory_snapshot"]:
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        print(f"[OK] Banco recriado em {DATABASE_PATH}")
        for table, n in counts.items():
            print(f"     {table:<20} -> {n} linhas")
    finally:
        conn.close()


if __name__ == "__main__":
    rebuild_database()
