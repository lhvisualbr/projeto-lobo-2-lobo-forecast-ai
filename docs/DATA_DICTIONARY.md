# Projeto Lobo 2 — DATA_DICTIONARY.md (Lobo Forecast AI)

Todas as tabelas abaixo contêm **exclusivamente dados sintéticos**, gerados por
`src/generate_data.py` com semente fixa (`RANDOM_SEED = 42`).

## `products` (30 linhas)

| Coluna | Tipo | Regra | Descrição |
|---|---|---|---|
| product_id | TEXT (PK) | único, formato `MATxxx` | Identificador do SKU fictício |
| product_name | TEXT | — | Nome descritivo fictício |
| category | TEXT | um de 5 valores | ABRASIVOS, SOLDAGEM, CORTE E USINAGEM, ELETRICA_BATERIAS, EPI_CONSUMIVEIS |
| unit | TEXT | — | Unidade de medida (UN, PAR, KG, CX, PCT) |
| unit_cost | REAL | > 0 | Custo unitário fictício, usado só para estimativas do estudo de caso |
| lead_time_days | INTEGER | > 0 | Prazo de entrega fictício do fornecedor |
| supplier | TEXT | — | Nome de fornecedor fictício |
| criticality | TEXT | LOW / MEDIUM / HIGH | Classificação de criticidade operacional |

## `calendar` (108 linhas: 104 conhecidas + 4 futuras)

| Coluna | Tipo | Descrição |
|---|---|---|
| week_id | INTEGER (PK) | Sequencial da semana |
| week_start | TEXT (data) | Segunda-feira da semana |
| week_end | TEXT (data) | Domingo da semana |
| year | INTEGER | Ano ISO |
| week_of_year | INTEGER | Semana ISO do ano |
| is_known | INTEGER (0/1) | 1 = semana com dados reais de consumo; 0 = semana futura (horizonte de forecast) |

## `consumption` (transações de retirada de material)

| Coluna | Tipo | Regra | Descrição |
|---|---|---|---|
| transaction_id | INTEGER (PK) | único | Identificador da retirada |
| consumption_date | TEXT (data) | — | Data da retirada |
| product_id | TEXT (FK → products) | deve existir em products | SKU consumido |
| quantity | INTEGER | > 0 | Quantidade retirada nesta transação |
| work_center | TEXT | um de 5 valores | MANUTENCAO, SOLDAGEM, FABRICACAO, MECANICA, ELETRICA |

Observação importante: quando um produto não tem nenhuma transação em uma
semana conhecida, isso **não é erro** — é demanda zero real, preservada na
série semanal derivada (não removida).

## `inventory_snapshot` (posição semanal de estoque)

| Coluna | Tipo | Regra | Descrição |
|---|---|---|---|
| snapshot_date | TEXT (data) | — | Data da posição (fim de semana) |
| product_id | TEXT (FK → products) | deve existir em products | SKU |
| on_hand | INTEGER | >= 0 | Estoque disponível fictício |
| in_transit | INTEGER | >= 0 | Quantidade fictícia já a caminho (pedido em aberto) |

Chave primária composta: (`snapshot_date`, `product_id`).

**Convenção temporal (V1.1, ver `src/generate_data.py::build_inventory_snapshot`):**
o snapshot registrado em `snapshot_date = week_end` representa a posição de
estoque **APÓS todos os movimentos daquela semana** — ou seja, já descontado
o consumo da própria semana e já somada qualquer chegada programada para essa
mesma semana. É análogo a um saldo bancário de fim de dia, que já reflete as
transações daquele dia: nenhuma informação de semanas **futuras** é usada.
`in_transit` é o que ainda resta em aberto imediatamente após esse
fechamento (não inclui a chegada que acabou de ser processada na mesma
semana). Essa convenção é validada por testes dedicados em
`tests/test_inventory_semantics.py` (inclusive um teste que muda o consumo
de uma semana futura e confirma que o snapshot de semanas anteriores não se
altera).

## Perfis de demanda usados na geração (não persistidos em tabela)

Cada produto recebe internamente, apenas durante a geração, um perfil de
giro (ALTO / MEDIO / BAIXO / INTERMITENTE), podendo ter tendência leve,
sazonalidade (~52 semanas) e ruído — para que a série tenha comportamento
plausível em vez de ruído puro. Ver `src/generate_data.py`,
`assign_demand_profiles()`.
