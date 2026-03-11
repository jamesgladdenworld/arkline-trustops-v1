"""
Arkline TrustOps v1 Configuration
"""

import os
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__ ).parent

# Paths
DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
DOCS_DIR = INPUT_DIR / "compliance_docs"
OUTPUT_DIR = DATA_DIR / "output"
CACHE_DIR = DATA_DIR / "cache"

# Create directories if they don't exist
for directory in [INPUT_DIR, DOCS_DIR, OUTPUT_DIR, CACHE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# API Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-opus-4-1-20250805"
MAX_TOKENS = 500
BATCH_SIZE = 10

# File paths
INPUT_QUESTIONNAIRE = INPUT_DIR / "questionnaire.xlsx"
OUTPUT_QUESTIONNAIRE = OUTPUT_DIR / "completed.xlsx"
CACHE_RESPONSES = CACHE_DIR / "responses.json"
CACHE_REVIEW_STATE = CACHE_DIR / "review_state.json"

# Processing settings
CONFIDENCE_THRESHOLD = 0.7
BATCH_PROCESSING = True
SAVE_INTERMEDIATE_RESULTS = True
