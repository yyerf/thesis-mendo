#!/usr/bin/env python3
"""Production WSGI entrypoint for Gunicorn."""

import os

# Suppress noisy ML library logs in production
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from web.app import app

# Gunicorn looks for the `app` variable in this module.
# Usage: gunicorn wsgi:app --bind 0.0.0.0:8000
