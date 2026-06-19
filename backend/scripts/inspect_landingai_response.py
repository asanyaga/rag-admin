#!/usr/bin/env python3
"""Inspect LandingAI parse_jobs raw response shape for a PDF.

Usage:
    VISION_AGENT_API_KEY=<key> uv run --directory backend python scripts/inspect_landingai_response.py
"""
import json
import os
import time
from collections import Counter, defaultdict
from pathlib import Path

from landingai_ade import LandingAIADE

API_KEY = os.environ["VISION_AGENT_API_KEY"]
DOCUMENT = Path(__file__).parent.parent.parent / "_scratch" / "Acorn-55-65.pdf"
OUTPUT = Path(__file__).parent.parent.parent / "_scratch" / "landingai_acorn_55_65_raw.json"


def summarise(raw: dict) -> None:
    chunks = raw.get("chunks") or []
    grounding = raw.get("grounding") or {}
    metadata = raw.get("metadata") or {}
    splits = raw.get("splits") or []

    print("\n=== TOP-LEVEL KEYS ===")
    print(list(raw.keys()))

    print("\n=== METADATA ===")
    print(json.dumps(metadata, indent=2))

    print("\n=== CHUNK COUNT & TYPES ===")
    type_counts = Counter(c.get("type", "?") for c in chunks)
    print(f"Total chunks: {len(chunks)}")
    for t, n in type_counts.most_common():
        print(f"  {t}: {n}")

    print("\n=== CHUNK TOP-LEVEL KEYS (union across all chunks) ===")
    all_chunk_keys: set = set()
    for c in chunks:
        all_chunk_keys |= set(c.keys())
    print(sorted(all_chunk_keys))

    print("\n=== GROUNDING TOP-LEVEL KEYS (union) ===")
    all_gr_keys: set = set()
    for v in grounding.values():
        if isinstance(v, dict):
            all_gr_keys |= set(v.keys())
    print(sorted(all_gr_keys))

    print("\n=== GROUNDING ENTRY TYPES ===")
    gr_type_counts = Counter(
        v.get("type", "?") for v in grounding.values() if isinstance(v, dict)
    )
    for t, n in gr_type_counts.most_common():
        print(f"  {t}: {n}")

    print("\n=== SAMPLE: first text chunk (full) ===")
    text_chunks = [c for c in chunks if c.get("type") == "text"]
    if text_chunks:
        c = text_chunks[0]
        print(json.dumps(c, indent=2))
        gr_entry = grounding.get(str(c.get("id", "")))
        if gr_entry:
            print("\n  -> grounding entry:")
            print(json.dumps(gr_entry, indent=2))

    print("\n=== SAMPLE: first table chunk (full) ===")
    table_chunks = [c for c in chunks if c.get("type") == "table"]
    if table_chunks:
        c = table_chunks[0]
        print(json.dumps(c, indent=2))
        gr_entry = grounding.get(str(c.get("id", "")))
        if gr_entry:
            print("\n  -> grounding entry:")
            print(json.dumps(gr_entry, indent=2))

    print("\n=== SAMPLE: first figure chunk (full) ===")
    figure_chunks = [c for c in chunks if c.get("type") == "figure"]
    if figure_chunks:
        c = figure_chunks[0]
        print(json.dumps(c, indent=2))
        gr_entry = grounding.get(str(c.get("id", "")))
        if gr_entry:
            print("\n  -> grounding entry:")
            print(json.dumps(gr_entry, indent=2))

    print("\n=== SPLITS ===")
    print(json.dumps(splits, indent=2))

    print("\n=== PER-CHUNK EXTRA KEYS (beyond id/type/markdown/grounding) ===")
    base_keys = {"id", "type", "markdown", "grounding"}
    extra_keys: set = set()
    for c in chunks:
        extra_keys |= set(c.keys()) - base_keys
    print(sorted(extra_keys) if extra_keys else "(none — only id/type/markdown/grounding)")

    print("\n=== CHUNK GROUNDING KEYS ===")
    chunk_gr_keys: set = set()
    for c in chunks:
        cg = c.get("grounding") or {}
        chunk_gr_keys |= set(cg.keys())
    print(sorted(chunk_gr_keys))

    print("\n=== HEADLINE GROUNDING ENTRY (first chunkText) ===")
    for k, v in grounding.items():
        if isinstance(v, dict) and v.get("type") == "chunkText":
            print(f"key={k}")
            print(json.dumps(v, indent=2))
            break

    print("\n=== HEADLINE GROUNDING ENTRY (first chunkTable) ===")
    for k, v in grounding.items():
        if isinstance(v, dict) and v.get("type") == "chunkTable":
            print(f"key={k}")
            print(json.dumps(v, indent=2))
            break

    print("\n=== HEADLINE GROUNDING ENTRY (first tableCell) ===")
    for k, v in grounding.items():
        if isinstance(v, dict) and v.get("type") == "tableCell":
            print(f"key={k}")
            print(json.dumps(v, indent=2))
            break


def main() -> None:
    client = LandingAIADE(apikey=API_KEY)

    print(f"Submitting {DOCUMENT.name} ...")
    job = client.parse_jobs.create(document=DOCUMENT, model="dpt-2-latest")
    job_id = job.job_id
    print(f"Job ID: {job_id}")

    while True:
        response = client.parse_jobs.get(job_id)
        print(f"  status={response.status}")
        if response.status == "completed":
            break
        if response.status == "failed":
            raise RuntimeError(f"Job {job_id} failed")
        time.sleep(5)

    raw = response.data.model_dump(mode="json")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRaw JSON saved to {OUTPUT}")

    summarise(raw)


if __name__ == "__main__":
    main()
