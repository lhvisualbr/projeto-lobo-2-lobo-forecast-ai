-- schema.sql
-- Lobo Forecast AI - modelo relacional (100% dados sintéticos)
-- Reexecutável: o banco pode ser apagado e recriado a partir daqui.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS inventory_snapshot;
DROP TABLE IF EXISTS consumption;
DROP TABLE IF EXISTS calendar;
DROP TABLE IF EXISTS products;

CREATE TABLE products (
    product_id      TEXT PRIMARY KEY,
    product_name    TEXT NOT NULL,
    category        TEXT NOT NULL,
    unit            TEXT NOT NULL,
    unit_cost       REAL NOT NULL CHECK (unit_cost > 0),
    lead_time_days  INTEGER NOT NULL CHECK (lead_time_days > 0),
    supplier        TEXT NOT NULL,
    criticality     TEXT NOT NULL CHECK (criticality IN ('LOW', 'MEDIUM', 'HIGH'))
);

CREATE TABLE calendar (
    week_id       INTEGER PRIMARY KEY,
    week_start    TEXT NOT NULL,
    week_end      TEXT NOT NULL,
    year          INTEGER NOT NULL,
    week_of_year  INTEGER NOT NULL,
    is_known      INTEGER NOT NULL CHECK (is_known IN (0, 1))
);

CREATE TABLE consumption (
    transaction_id     INTEGER PRIMARY KEY,
    consumption_date   TEXT NOT NULL,
    product_id         TEXT NOT NULL,
    quantity           INTEGER NOT NULL CHECK (quantity > 0),
    work_center        TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products (product_id)
);

CREATE TABLE inventory_snapshot (
    snapshot_date   TEXT NOT NULL,
    product_id      TEXT NOT NULL,
    on_hand         INTEGER NOT NULL CHECK (on_hand >= 0),
    in_transit      INTEGER NOT NULL CHECK (in_transit >= 0),
    PRIMARY KEY (snapshot_date, product_id),
    FOREIGN KEY (product_id) REFERENCES products (product_id)
);

CREATE INDEX idx_consumption_product_date ON consumption (product_id, consumption_date);
CREATE INDEX idx_inventory_product_date ON inventory_snapshot (product_id, snapshot_date);
