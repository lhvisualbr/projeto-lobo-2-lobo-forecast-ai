-- analysis_queries.sql
-- Lobo Forecast AI - consultas que respondem perguntas reais de negócio.
-- Todas rodam sobre database/lobo_forecast.db (SQLite).

-- 1. Consumo semanal por produto (agregando as transações diárias na semana)
SELECT
    c.week_start,
    p.product_id,
    p.product_name,
    SUM(cons.quantity) AS total_consumido
FROM consumption cons
JOIN products p ON p.product_id = cons.product_id
JOIN calendar c ON cons.consumption_date BETWEEN c.week_start AND c.week_end
GROUP BY c.week_start, p.product_id
ORDER BY c.week_start, p.product_id;

-- 2. Consumo semanal por categoria
SELECT
    c.week_start,
    p.category,
    SUM(cons.quantity) AS total_consumido
FROM consumption cons
JOIN products p ON p.product_id = cons.product_id
JOIN calendar c ON cons.consumption_date BETWEEN c.week_start AND c.week_end
GROUP BY c.week_start, p.category
ORDER BY c.week_start, p.category;

-- 3. Custo estimado do consumo (quantidade x custo unitário fictício)
SELECT
    p.product_id,
    p.product_name,
    SUM(cons.quantity) AS quantidade_total,
    p.unit_cost,
    ROUND(SUM(cons.quantity) * p.unit_cost, 2) AS custo_estimado
FROM consumption cons
JOIN products p ON p.product_id = cons.product_id
GROUP BY p.product_id
ORDER BY custo_estimado DESC;

-- 4. Ranking de materiais por volume consumido
SELECT
    p.product_id,
    p.product_name,
    SUM(cons.quantity) AS quantidade_total
FROM consumption cons
JOIN products p ON p.product_id = cons.product_id
GROUP BY p.product_id
ORDER BY quantidade_total DESC
LIMIT 10;

-- 5. Ranking de materiais por valor (custo fictício acumulado)
SELECT
    p.product_id,
    p.product_name,
    ROUND(SUM(cons.quantity) * p.unit_cost, 2) AS valor_estimado
FROM consumption cons
JOIN products p ON p.product_id = cons.product_id
GROUP BY p.product_id
ORDER BY valor_estimado DESC
LIMIT 10;

-- 6. Participação de cada categoria no consumo total
SELECT
    p.category,
    SUM(cons.quantity) AS quantidade_total,
    ROUND(100.0 * SUM(cons.quantity) / (SELECT SUM(quantity) FROM consumption), 2) AS participacao_pct
FROM consumption cons
JOIN products p ON p.product_id = cons.product_id
GROUP BY p.category
ORDER BY participacao_pct DESC;

-- 7. Participação de cada centro de trabalho no consumo total
SELECT
    work_center,
    SUM(quantity) AS quantidade_total,
    ROUND(100.0 * SUM(quantity) / (SELECT SUM(quantity) FROM consumption), 2) AS participacao_pct
FROM consumption
GROUP BY work_center
ORDER BY participacao_pct DESC;

-- 8. Materiais com muitas semanas sem consumo (candidatos a demanda intermitente)
-- (conta semanas conhecidas do calendário sem nenhuma transação para o produto)
SELECT
    p.product_id,
    p.product_name,
    (SELECT COUNT(*) FROM calendar WHERE is_known = 1) AS semanas_conhecidas,
    COUNT(DISTINCT c.week_start) AS semanas_com_consumo,
    (SELECT COUNT(*) FROM calendar WHERE is_known = 1) - COUNT(DISTINCT c.week_start) AS semanas_sem_consumo
FROM products p
LEFT JOIN consumption cons ON cons.product_id = p.product_id
LEFT JOIN calendar c ON cons.consumption_date BETWEEN c.week_start AND c.week_end
GROUP BY p.product_id
ORDER BY semanas_sem_consumo DESC;

-- 9. Estoque atual (última snapshot) versus consumo médio semanal
SELECT
    p.product_id,
    p.product_name,
    last_snapshot.on_hand,
    last_snapshot.in_transit,
    ROUND(avg_consumo.media_semanal, 2) AS consumo_medio_semanal
FROM products p
JOIN (
    SELECT product_id, on_hand, in_transit
    FROM inventory_snapshot
    WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM inventory_snapshot)
) last_snapshot ON last_snapshot.product_id = p.product_id
JOIN (
    SELECT
        cons.product_id,
        SUM(cons.quantity) * 1.0 / (SELECT COUNT(*) FROM calendar WHERE is_known = 1) AS media_semanal
    FROM consumption cons
    GROUP BY cons.product_id
) avg_consumo ON avg_consumo.product_id = p.product_id
ORDER BY (last_snapshot.on_hand * 1.0 / NULLIF(avg_consumo.media_semanal, 0)) ASC;

-- 10. Itens potencialmente abaixo da necessidade do lead time
-- (estoque atual insuficiente para cobrir o consumo médio durante o lead time do fornecedor)
SELECT
    p.product_id,
    p.product_name,
    p.lead_time_days,
    last_snapshot.on_hand,
    ROUND(avg_consumo.media_semanal * (p.lead_time_days / 7.0), 2) AS demanda_esperada_lead_time
FROM products p
JOIN (
    SELECT product_id, on_hand
    FROM inventory_snapshot
    WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM inventory_snapshot)
) last_snapshot ON last_snapshot.product_id = p.product_id
JOIN (
    SELECT
        cons.product_id,
        SUM(cons.quantity) * 1.0 / (SELECT COUNT(*) FROM calendar WHERE is_known = 1) AS media_semanal
    FROM consumption cons
    GROUP BY cons.product_id
) avg_consumo ON avg_consumo.product_id = p.product_id
WHERE last_snapshot.on_hand < (avg_consumo.media_semanal * (p.lead_time_days / 7.0))
ORDER BY demanda_esperada_lead_time DESC;
