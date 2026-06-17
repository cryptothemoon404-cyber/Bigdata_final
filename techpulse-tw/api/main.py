"""
TechPulse TW - FastAPI Backend
Serves aggregated analytics data to the frontend dashboard.

Endpoints
---------
GET /api/health                  — liveness check
GET /api/skills                  — top-N skill demand ranking
GET /api/salary-distribution     — salary bucket counts
GET /api/industries              — industry breakdown
GET /api/companies               — top hiring companies
GET /api/skill-salary            — skill vs avg salary correlation
GET /api/summary                 — high-level stats card

All data is loaded from CSV files produced by the pipeline.
In production these would query PostgreSQL directly via asyncpg.
"""

import os
import csv
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="TechPulse TW API",
    description="Taiwan Tech Job Market Intelligence — aggregated analytics from 104.com.tw",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))


# ── Data loading helpers ──────────────────────────────────────────────────────

def load_csv(filename: str) -> List[Dict]:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def cast_int_fields(rows: List[Dict], fields: List[str]) -> List[Dict]:
    for row in rows:
        for field in fields:
            if field in row:
                try:
                    row[field] = int(row[field])
                except (ValueError, TypeError):
                    row[field] = 0
    return rows


def cast_float_fields(rows: List[Dict], fields: List[str]) -> List[Dict]:
    for row in rows:
        for field in fields:
            if field in row:
                try:
                    row[field] = float(row[field])
                except (ValueError, TypeError):
                    row[field] = 0.0
    return rows


# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/skills")
def get_skill_demand(top: int = Query(20, ge=1, le=50)):
    """
    Return top-N skills by job posting count, with % share.
    """
    rows = load_csv("skill_demand.csv")
    rows = cast_int_fields(rows, ["job_count"])
    rows = cast_float_fields(rows, ["share_pct"])
    return rows[:top]


@app.get("/api/salary-distribution")
def get_salary_distribution():
    """
    Salary bucket distribution across all scraped jobs.
    """
    rows = load_csv("salary_distribution.csv")
    rows = cast_int_fields(rows, ["count"])
    return rows


@app.get("/api/industries")
def get_industries(top: int = Query(15, ge=1, le=30)):
    """
    Top industries by number of open tech positions.
    """
    rows = load_csv("industry_breakdown.csv")
    rows = cast_int_fields(rows, ["job_count"])
    return rows[:top]


@app.get("/api/companies")
def get_companies(top: int = Query(15, ge=1, le=30)):
    """
    Top hiring companies by open position count.
    """
    rows = load_csv("top_companies.csv")
    rows = cast_int_fields(rows, ["open_positions"])
    return rows[:top]


@app.get("/api/skill-salary")
def get_skill_salary(top: int = Query(15, ge=1, le=30)):
    """
    Skills ranked by average minimum monthly salary (TWD).
    Only skills with ≥3 salary-disclosed postings are included.
    """
    rows = load_csv("skill_salary.csv")
    rows = cast_int_fields(rows, ["avg_salary_min", "sample_size"])
    return rows[:top]


@app.get("/api/summary")
def get_summary():
    """
    High-level stats card for the dashboard hero section.
    """
    meta_path = os.path.join(DATA_DIR, "pipeline_meta.json")
    if not os.path.exists(meta_path):
        return {"total_jobs": 0, "last_updated": "N/A", "skills_tracked": 0}

    with open(meta_path) as f:
        meta = json.load(f)

    skill_rows = load_csv("skill_demand.csv")
    return {
        "total_jobs":     meta.get("total_jobs_processed", 0),
        "last_updated":   meta.get("pipeline_run_at", "N/A"),
        "skills_tracked": len(skill_rows),
    }


# ── Static frontend serving ───────────────────────────────────────────────────

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

@app.get("/", include_in_schema=False)
def serve_index():
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "TechPulse TW API is running. Visit /docs for API docs."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
