"""Allow running: python -m ingestion [optional_file_path]"""
import sys
from ingestion import run_ingestion

target = sys.argv[1] if len(sys.argv) > 1 else None
run_ingestion(target)
