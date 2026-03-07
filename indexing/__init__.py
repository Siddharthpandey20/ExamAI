"""
indexing — Stage 3: Embed structured knowledge into ChromaDB + SQLite.

Parses enriched markdown from knowledge/, extracts per-slide metadata,
generates sentence-transformer embeddings, and stores everything in:
  - SQLite  → processing state, raw data, PYQ records, computed scores
  - ChromaDB → embeddings + metadata for vector search
"""
