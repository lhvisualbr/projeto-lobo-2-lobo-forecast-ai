"""
Smoke test do dashboard: garante que app.py está sintaticamente correto
e importa sem erro de sintaxe. Não executa a UI (isso exige um servidor
Streamlit real) — para isso, ver docs/TEST_REPORT.md (teste manual com
Playwright, screenshots reais em images/dashboard_*.png).
"""

import ast
from pathlib import Path

APP_PATH = Path(__file__).resolve().parent.parent / "src" / "app.py"


def test_app_file_exists():
    assert APP_PATH.exists()


def test_app_has_valid_python_syntax():
    source = APP_PATH.read_text(encoding="utf-8")
    ast.parse(source)  # levanta SyntaxError se o arquivo estiver quebrado


def test_app_references_all_required_pages():
    source = APP_PATH.read_text(encoding="utf-8")
    required_pages = ["Visão Geral", "Forecast", "Estoque", "Qualidade do Modelo", "Dados"]
    for page_name in required_pages:
        assert page_name in source
