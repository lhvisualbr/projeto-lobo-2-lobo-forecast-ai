"""
Testes do banco SQLite: schema, integridade referencial e contagens.
"""

import sqlite3

import pytest

from config import DATABASE_PATH


@pytest.fixture(scope="module")
def conn():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON;")
    yield connection
    connection.close()


def test_database_file_exists():
    assert DATABASE_PATH.exists()


def test_all_tables_exist(conn):
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()
    }
    expected = {"products", "calendar", "consumption", "inventory_snapshot"}
    assert expected.issubset(tables)


def test_products_row_count(conn):
    count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    assert count == 30


def test_foreign_keys_are_enabled(conn):
    fk_status = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
    assert fk_status == 1


def test_no_orphan_consumption_rows(conn):
    orphan_count = conn.execute(
        """
        SELECT COUNT(*) FROM consumption c
        LEFT JOIN products p ON p.product_id = c.product_id
        WHERE p.product_id IS NULL
        """
    ).fetchone()[0]
    assert orphan_count == 0


def test_no_negative_inventory(conn):
    negative_count = conn.execute(
        "SELECT COUNT(*) FROM inventory_snapshot WHERE on_hand < 0 OR in_transit < 0"
    ).fetchone()[0]
    assert negative_count == 0


def test_check_constraint_blocks_invalid_criticality(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO products
                (product_id, product_name, category, unit, unit_cost,
                 lead_time_days, supplier, criticality)
            VALUES ('MATXXX', 'teste', 'ABRASIVOS', 'UN', 10.0, 5, 'Fornecedor Teste', 'INVALID')
            """
        )
        conn.rollback()


def test_foreign_key_constraint_blocks_orphan_insert(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO consumption (transaction_id, consumption_date, product_id, quantity, work_center)
            VALUES (999999999, '2026-01-01', 'MAT_INEXISTENTE', 1, 'MANUTENCAO')
            """
        )
        conn.rollback()
