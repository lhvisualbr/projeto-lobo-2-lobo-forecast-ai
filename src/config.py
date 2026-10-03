"""
config.py
Configurações centrais do Lobo Forecast AI.

Concentrar aqui os parâmetros evita "números mágicos" espalhados pelo código
e torna o projeto reproduzível: mudar uma constante aqui é o único lugar
necessário para reexecutar tudo de forma consistente.
"""

from pathlib import Path

# --------------------------------------------------------------------------
# Reprodutibilidade
# --------------------------------------------------------------------------
RANDOM_SEED = 42

# --------------------------------------------------------------------------
# Caminhos
# --------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = ROOT_DIR / "data" / "raw"
DATA_PROCESSED_DIR = ROOT_DIR / "data" / "processed"
DATABASE_DIR = ROOT_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "lobo_forecast.db"
SQL_DIR = ROOT_DIR / "sql"
RESULTS_DIR = ROOT_DIR / "results"
IMAGES_DIR = ROOT_DIR / "images"

# --------------------------------------------------------------------------
# Período do estudo de caso
# --------------------------------------------------------------------------
# 24 meses de histórico sintético, terminando na semana mais recente simulada.
HISTORY_MONTHS = 24
# Horizonte de previsão futura (não existe consumo real para essas semanas).
FORECAST_HORIZON_WEEKS = 4
# Últimas N semanas do histórico usadas como teste temporal (nunca embaralhado).
TEST_WEEKS = 8

# --------------------------------------------------------------------------
# Backtest multi-horizon (rolling-origin) — V1.1
# --------------------------------------------------------------------------
# Nº mínimo de semanas de histórico ANTES de uma origem de backtest, para
# garantir um treino com volume razoável de linhas completas (com lag_52).
BACKTEST_MIN_TRAIN_WEEK = 60
# Horizontes avaliados no backtest recursivo (H+1 a H+4, igual ao horizonte
# de produção do forecast).
BACKTEST_HORIZONS = 4

# Data de "hoje" fictícia usada como fim do histórico conhecido.
# Fixa para manter o projeto 100% reproduzível entre execuções.
SIMULATED_TODAY = "2026-09-13"  # domingo - fim da última semana completa conhecida

# --------------------------------------------------------------------------
# Catálogo de produtos (SKUs)
# --------------------------------------------------------------------------
N_PRODUCTS = 30

CATEGORIES = [
    "ABRASIVOS",
    "SOLDAGEM",
    "CORTE E USINAGEM",
    "ELETRICA_BATERIAS",
    "EPI_CONSUMIVEIS",
]

UNITS = ["UN", "PAR", "KG", "CX", "PCT"]

CRITICALITY_LEVELS = ["LOW", "MEDIUM", "HIGH"]

WORK_CENTERS = ["MANUTENCAO", "SOLDAGEM", "FABRICACAO", "MECANICA", "ELETRICA"]

SUPPLIERS = [
    "Fornecedor Atlas",
    "Fornecedor Vetor",
    "Fornecedor Trilha",
    "Fornecedor Cronos",
    "Fornecedor Pilar",
    "Fornecedor Bravo",
]

# --------------------------------------------------------------------------
# Motor de reposição (parâmetros atuais)
# --------------------------------------------------------------------------
DEFAULT_SERVICE_FACTOR = 1.65  # aproximação de ~95% de nível de serviço
REVIEW_PERIOD_WEEKS = 1
