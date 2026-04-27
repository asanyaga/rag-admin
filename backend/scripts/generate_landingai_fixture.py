#!/usr/bin/env python3
"""One-off script: call Landing AI parse_jobs with cleanshelf image, save fixture JSON.

Usage:
    VISION_AGENT_API_KEY=<key> uv run --directory backend python scripts/generate_landingai_fixture.py
"""
import json
import os
import time
from pathlib import Path

from landingai_ade import LandingAIADE

API_KEY = os.environ["VISION_AGENT_API_KEY"]
DOCUMENT = Path(__file__).parent.parent.parent / "_scratch" / "cleanshelf-12-4-26.jpg"
OUTPUT = Path(__file__).parent.parent / "app" / "cdm" / "eval" / "fixtures" / "landing_ai_cleanshelf.json"


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
    print(f"Saved to {OUTPUT}")
    print(f"  chunks:    {len(raw.get('chunks', []))}")
    print(f"  pages:     {raw.get('metadata', {}).get('page_count')}")
    print(f"  credits:   {raw.get('metadata', {}).get('credit_usage')}")


if __name__ == "__main__":
    main()
