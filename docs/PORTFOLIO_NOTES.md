# Projeto Lobo 2 — PORTFOLIO_NOTES.md (Lobo Forecast AI)

## Como apresentar o projeto (V1.1 — pronto)

> "Lobo Forecast AI — estudo de caso autoral de previsão de consumo e
> reposição industrial (dados 100% sintéticos). Estruturei dados
> sintéticos reprodutíveis, banco SQLite com chaves e constraints,
> pipeline de série temporal sem vazamento, três baselines e um modelo
> RandomForest avaliado sob DOIS protocolos: teste one-step-ahead (WAPE
> 27,56% vs. 27,66% da melhor baseline) e um backtest rolling-origin
> multi-horizon H+1 a H+4 que replica o uso real (forecast recursivo) —
> onde o modelo vence nos horizontes mais próximos, mas a baseline simples
> vence em H+3/H+4 por margem pequena, resultado reportado sem maquiagem
> nos dois sentidos. A partir do forecast, construí um motor de reposição
> auditável (estoque de segurança, estoque-alvo, prioridade, com as
> convenções de risco documentadas) e um dashboard em Streamlit com 5
> páginas. 59 testes automatizados (incluindo teste de integração de
> pipeline), lint limpo, CI configurada, pipeline reproduzível do zero em
> pasta limpa com dependências fixadas."

Essa versão está pronta para submissão a uma nova auditoria técnica
independente antes de qualquer publicação (ver `docs/CHANGELOG.md`).

## Tecnologias que já pode citar com segurança

- Python (Pandas, NumPy) para geração e validação de dados.
- SQL / SQLite (schema, chaves estrangeiras, constraints, consultas
  analíticas).
- Testes automatizados com pytest (59 testes, incluindo teste de
  integração de pipeline via subprocess) e lint limpo (ruff).
- Modelagem de dados para série temporal (calendário semanal, preservação
  de semanas zero, convenção temporal explícita de snapshot de estoque).
- Metodologia de avaliação de forecast: diferença entre teste
  one-step-ahead e backtest rolling-origin multi-horizon.
- CI com GitHub Actions; dependências fixadas para reprodutibilidade.

## Perguntas de entrevista que já deve conseguir responder

- Por que existe uma tabela `calendar` separada?
  → Para garantir que nenhuma semana "some" da série, mesmo com consumo
  zero — essencial para forecasting correto depois.
- Por que os dados foram gerados sinteticamente com semente fixa?
  → Reprodutibilidade: qualquer pessoa consegue rodar o gerador e obter
  exatamente os mesmos dados, sem depender de acesso a dados reais.
- Como você garante integridade referencial?
  → Foreign keys ativas no SQLite (`PRAGMA foreign_keys = ON`), testadas
  explicitamente (inserção órfã deve falhar).
- Por que o estoque não é só aleatório?
  → Ele segue uma lógica simples de ponto de reposição atrelada ao
  consumo real gerado, para que a posição de estoque faça sentido.
- Qual a diferença entre a avaliação one-step-ahead e o backtest
  multi-horizon, e por que os dois existem?
  → One-step-ahead sempre usa o valor real da semana anterior para prever
  a próxima — mede a capacidade "pura" do modelo, mas não reflete o uso
  real. O backtest multi-horizon simula o uso real: forecast recursivo de
  4 semanas a partir de várias origens, usando a própria previsão como
  pseudo-histórico para os passos seguintes. Os dois números não devem
  ser comparados diretamente.
- Por que a classificação de risco de ruptura ignora `in_transit`, mas o
  cálculo de quantidade sugerida não?
  → Decisão de design documentada: sem ETA por pedido, não há garantia de
  que o material em trânsito chegue dentro da janela de risco — então a
  classificação de risco é conservadora e o ignora. Já a quantidade
  sugerida desconta `in_transit` porque ele é uma quantidade já
  comprometida que eventualmente chegará.

## Perguntas já respondidas com número real

- Qual baseline venceu entre as baselines (one-step-ahead)? → média móvel
  de 4 semanas (WAPE 0,2766), batendo naive (0,3438) e sazonal (0,3522).
- O modelo superou a melhor baseline no teste one-step-ahead? → sim, por
  margem pequena (WAPE 0,2756 vs. 0,2766).
- E no backtest multi-horizon? → depende do horizonte: o modelo vence em
  H+1 (24,14%) e H+2 (24,78%), mas a média móvel de 4 semanas vence em
  H+3 (25,38% vs. 25,68%) e H+4 (25,34% vs. 25,81%). No consolidado, o
  modelo vence por margem mínima (25,10% vs. 25,15%).
- Onde o modelo falha mais? → SKUs de baixo giro/intermitentes, onde o
  WAPE passa de 1 em alguns casos (erro maior que o próprio volume real).
- Quantos SKUs ficaram críticos? → 3 (Máscara de Solda Filtro Escuro
  MAT010, Bateria para Ferramenta 18V MAT019, Protetor Auricular Tipo
  Plug MAT027), no cenário sintético atual; 9 em prioridade média; 17 em
  baixa; 1 em alta.
- Qual o custo estimado total de reposição sugerida? → R$ 21.268,45
  (fictício, baseado em `unit_cost` sintético).
- Por que esse número mudou desde a V1.0 (era R$ 9.866,72, 1 crítico)?
  → A auditoria da V1.1 corrigiu um bug real de desalinhamento temporal
  no snapshot de estoque, que estava subestimando o risco de ruptura. O
  número novo é o correto.

## Perguntas que ainda exigem cautela

- "Isso escala para produção?" → não sem revisão: `service_factor` único,
  sem lote mínimo/contratos reais, sem ETA por pedido em trânsito — ver
  `docs/LIMITATIONS.md`. Seja honesto sobre isso se perguntarem; não venda
  como pronto para produção.
- "O modelo de ML é melhor que uma média móvel?" → depende do horizonte,
  e a diferença é pequena nos dois protocolos de avaliação. Não afirme
  superioridade forte — os números não sustentam isso.

Ver `MODEL_CARD.md` e `LIMITATIONS.md` para os detalhes completos.

## O que dominar antes de colocar no currículo (checklist de estudo)

- [ ] Explicar cada consulta de `analysis_queries.sql` sem ler a tela.
- [ ] Explicar por que `shift(1)` vem antes de `rolling()` (evitar leakage).
- [ ] Explicar a diferença entre teste one-step-ahead e backtest
      rolling-origin multi-horizon, e por que ambos existem.
- [ ] Explicar WAPE, MAE e viés com um exemplo numérico simples.
- [ ] Explicar a fórmula do estoque-alvo e por que ela usa `sqrt(lead_time)`.
- [ ] Explicar por que a classificação de risco ignora `in_transit` mas a
      quantidade sugerida não.
- [ ] Explicar a convenção temporal do `inventory_snapshot` (posição
      registrada APÓS os movimentos da própria semana).
- [ ] Explicar por que a reposição é uma sugestão, não uma decisão automática.
