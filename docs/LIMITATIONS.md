# Projeto Lobo 2 — LIMITATIONS.md (Lobo Forecast AI)

Este é um estudo de caso educacional/portfólio. Ele **não** modela
completamente, e isso é intencional:

- Lote mínimo de compra e contratos reais com fornecedores.
- Validade de materiais, capacidade de armazenagem física e capacidade
  financeira da empresa fictícia.
- Promoções, paradas de produção reais ou urgências operacionais específicas
  de uma empresa real.
- Substituição entre materiais equivalentes.
- Rupturas históricas reais ou seu impacto em produção.

## Sobre os dados

- 100% sintéticos, gerados com semente fixa (reprodutíveis, mas não reais).
  **Os dados são simulados para fins de demonstração e não validam
  desempenho em uma operação real** — nenhuma métrica deste projeto deve
  ser extrapolada para uma previsão de comportamento em produção real.
- O gerador foi projetado para produzir comportamentos plausíveis (giro
  alto/médio/baixo, intermitência, tendência leve, sazonalidade), mas não
  captura toda a complexidade de uma cadeia de suprimentos real.
- O estoque sintético (`inventory_snapshot`) usa uma lógica simplificada de
  ponto de reposição só para ficar coerente com o consumo gerado — **não**
  é o motor de reposição do projeto (ver seção própria abaixo). Desde a
  V1.1, o snapshot de cada semana representa a posição APÓS os movimentos
  daquela própria semana (ver `docs/DATA_DICTIONARY.md`, seção
  `inventory_snapshot`, e os testes em `tests/test_inventory_semantics.py`).

## Sobre o modelo e o forecast

- O modelo de ML (RandomForest) supera a melhor baseline (média móvel de
  4 semanas) por margem pequena no teste one-step-ahead (WAPE 0,2756 vs.
  0,2766) e no backtest multi-horizon consolidado (WAPE 0,2510 vs.
  0,2515). **Não afirmamos superioridade significativa** — a margem é
  pequena demais para isso, e no backtest por horizonte a média móvel
  chega a VENCER o modelo em H+3 e H+4 (ver `MODEL_CARD.md`). Isso foi
  reportado como está, nos dois sentidos — não foi maquiado nem escondido.
- **Duas avaliações diferentes e não intercambiáveis** (V1.1): a avaliação
  one-step-ahead (`run_evaluation.py`) mede a capacidade do modelo de
  acertar UMA semana à frente usando sempre o valor real da semana
  anterior; o backtest rolling-origin multi-horizon
  (`backtest_multihorizon.py`) mede o cenário real de uso — forecast
  recursivo de 4 semanas, sem usar nenhum valor real futuro à origem. Os
  números das duas avaliações não devem ser misturados nem comparados
  diretamente. Ver `MODEL_CARD.md`, seção "Duas avaliações diferentes".
- **Performance do backtest (V1.1.1):** o ambiente de desenvolvimento
  usado tem 1 CPU lógica disponível, então não há ganho a esperar de
  paralelismo entre origens do rolling-origin — a otimização de
  performance feita foi de redução de trabalho redundante (predição em
  lote, lookup vetorizado), não de paralelização. Em uma máquina com mais
  núcleos, os tempos absolutos mudam, mas o ganho relativo da otimização
  deve se manter. Ver `docs/PERFORMANCE_AUDIT.md`.
- Croston/SBA não foi implementada: a média móvel de 4 semanas já se
  mostrou competitiva mesmo nos SKUs intermitentes gerados, então a
  complexidade extra do Croston não teve evidência de necessidade nesta
  base de dados.
- O modelo tem desempenho pior (WAPE alto) nos SKUs de baixo giro/
  intermitentes — comportamento esperado e documentado no `MODEL_CARD.md`,
  não corrigido artificialmente.
- O forecast recursivo assume que o comportamento observado no histórico
  se mantém; qualquer mudança estrutural futura (nova máquina, novo
  processo) não é capturada.

## Sobre o motor de reposição

- `demand_std` é calculado sobre a variabilidade semanal histórica real
  (24 meses), não estimado de forma teórica.
- `service_factor` fixo (1,65, ~95% de nível de serviço) é um parâmetro de
  cenário — em um contexto real, variaria por criticidade do item, o que
  não foi implementado nesta versão.
- **Limitação de estoque em trânsito (V1.1):** o projeto não possui ETA
  (data de chegada) por pedido — apenas uma quantidade agregada de
  `in_transit`. Sem essa informação, o sistema não tem como saber
  exatamente QUANDO cada quantidade em trânsito estará disponível. Por
  isso, a classificação de risco de ruptura (CRÍTICA/ALTA) ignora
  deliberadamente `in_transit` (abordagem conservadora), enquanto o
  cálculo de `suggested_order` desconta `in_transit` do estoque-alvo
  (assumindo que ele eventualmente chegará). Essa é uma decisão de design
  documentada, não uma inconsistência — ver docstring de
  `classify_priority()` em `src/replenishment.py`.
- O motor **não considera** lote mínimo de compra, contratos com
  fornecedor, nem múltiplos pedidos em trânsito simultâneos com ETAs
  diferentes entre si.
- Resultado é sempre uma sugestão auditável — nunca uma compra automática.

## Sobre o dashboard

- Roda apenas localmente (`streamlit run app.py`) — não há deploy público
  nesta versão (ver "Próximos passos" no `README.md`).
- Os dados são recarregados via `@st.cache_data`; se o pipeline for
  reexecutado (novo forecast/reposição), é preciso reiniciar o Streamlit
  para refletir os novos resultados.

## Uso pretendido

Estudo de caso de portfólio para demonstrar SQL, engenharia de dados,
forecasting e apoio à decisão de estoque. **Nunca** deve ser apresentado
como um otimizador empresarial pronto para produção.
