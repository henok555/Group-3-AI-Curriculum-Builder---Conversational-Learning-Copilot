"""Pytest root marker: ensures the repo root is on sys.path so tests can
import the `app` package whether run as `pytest` or `python -m pytest`."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
