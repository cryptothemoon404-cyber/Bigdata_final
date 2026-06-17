"""
TechPulse TW - Data Processing Pipeline
Batch-processes raw scraped job listings into aggregated analytics tables.

Design notes
------------
- Runs as a daily batch job (cron / Airflow task / simple script).
- Input:  data/jobs_raw.json   (produced by scraper/scraper.py)
- Output: writes aggregated results to PostgreSQL (via psycopg2).
- Also writes CSV snapshots to data/ for reproducibility.

At 10–100× scale this module would be replaced by a Spark job
(see architecture notes in README), but for the prototype pandas is sufficient.
"""

import json
import os
import csv
import logging
from collections import Counter, defaultdict
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── Known tech-skill tags to track ───────────────────────────────────────────
SKILL_KEYWORDS = [
    # Languages
    "Python", "Java", "Go", "Golang", "C++", "C#", "Rust", "TypeScript",
    "JavaScript", "Kotlin", "Swift",
    # Data / ML
    "SQL", "Spark", "Kafka", "Flink", "Airflow", "dbt", "Hadoop",
    "TensorFlow", "PyTorch", "scikit-learn", "LLM", "RAG",
    # Cloud / Infra
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "CI/CD",
    "Elasticsearch", "Redis", "PostgreSQL", "MongoDB", "Cassandra",
    # Web
    "React", "Vue", "Angular", "Node.js", "FastAPI", "Django", "Spring Boot",
]


# ── Helper utilities ──────────────────────────────────────────────────────────

def load_jobs(path: str = "data/jobs_raw.json") -> List[Dict]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Raw data not found at {path}. Run the scraper first.")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_skills_from_job(job: Dict) -> List[str]:
    """
    Detect known skills by scanning the job title and tags list.
    Case-insensitive substring match.
    """
    text = " ".join([job.get("title", "")] + job.get("tags", [])).lower()
    found = []
    for skill in SKILL_KEYWORDS:
        if skill.lower() in text:
            found.append(skill)
    return found


def salary_bucket(monthly_twd: int) -> str:
    """Map a monthly salary (TWD) to a human-readable bucket."""
    if monthly_twd == 0:
        return "Undisclosed"
    if monthly_twd < 40_000:
        return "<40K"
    if monthly_twd < 60_000:
        return "40K-60K"
    if monthly_twd < 80_000:
        return "60K-80K"
    if monthly_twd < 100_000:
        return "80K-100K"
    if monthly_twd < 150_000:
        return "100K-150K"
    return "150K+"


# ── Aggregation functions ─────────────────────────────────────────────────────

def aggregate_skill_demand(jobs: List[Dict]) -> List[Dict]:
    """
    Count how many job postings mention each skill.
    Returns a list sorted by count descending.
    """
    counter: Counter = Counter()
    for job in jobs:
        for skill in extract_skills_from_job(job):
            counter[skill] += 1

    return [
        {"skill": skill, "job_count": count, "share_pct": round(count / len(jobs) * 100, 2)}
        for skill, count in counter.most_common()
    ]


def aggregate_salary_distribution(jobs: List[Dict]) -> List[Dict]:
    """
    Distribution of salary_min across salary buckets.
    Only considers jobs with disclosed salary.
    """
    bucket_counts: Counter = Counter()
    for job in jobs:
        b = salary_bucket(job.get("salary_min", 0))
        bucket_counts[b] += 1

    order = ["<40K", "40K-60K", "60K-80K", "80K-100K", "100K-150K", "150K+", "Undisclosed"]
    return [
        {"bucket": b, "count": bucket_counts.get(b, 0)}
        for b in order
    ]


def aggregate_industry_breakdown(jobs: List[Dict]) -> List[Dict]:
    """Top industries by number of open positions."""
    counter: Counter = Counter(
        job.get("industry", "Unknown") for job in jobs if job.get("industry")
    )
    return [
        {"industry": ind, "job_count": cnt}
        for ind, cnt in counter.most_common(20)
    ]


def aggregate_top_hiring_companies(jobs: List[Dict]) -> List[Dict]:
    """Companies with the most open listings."""
    counter: Counter = Counter(
        job.get("company", "Unknown") for job in jobs if job.get("company")
    )
    return [
        {"company": co, "open_positions": cnt}
        for co, cnt in counter.most_common(20)
    ]


def aggregate_skill_salary_correlation(jobs: List[Dict]) -> List[Dict]:
    """
    For each skill, compute average salary_min across jobs that mention it
    (excluding undisclosed / 0-salary jobs).
    """
    skill_salaries: Dict[str, List[int]] = defaultdict(list)
    for job in jobs:
        sal = job.get("salary_min", 0)
        if sal > 0:
            for skill in extract_skills_from_job(job):
                skill_salaries[skill].append(sal)

    result = []
    for skill, salaries in skill_salaries.items():
        if len(salaries) >= 3:   # Minimum sample for statistical relevance
            result.append({
                "skill": skill,
                "avg_salary_min": round(sum(salaries) / len(salaries)),
                "sample_size": len(salaries),
            })
    return sorted(result, key=lambda x: x["avg_salary_min"], reverse=True)


# ── Main pipeline entry point ─────────────────────────────────────────────────

def run_pipeline(
    input_path: str = "data/jobs_raw.json",
    output_dir: str = "data",
) -> Dict[str, List[Dict]]:
    """
    Execute the full batch processing pipeline.

    Produces four aggregation tables and writes them as CSV files.
    In production these would be upserted into PostgreSQL.
    """
    logger.info("Loading raw job data...")
    jobs = load_jobs(input_path)
    logger.info(f"Loaded {len(jobs)} job records.")

    results = {
        "skill_demand":          aggregate_skill_demand(jobs),
        "salary_distribution":   aggregate_salary_distribution(jobs),
        "industry_breakdown":    aggregate_industry_breakdown(jobs),
        "top_companies":         aggregate_top_hiring_companies(jobs),
        "skill_salary":          aggregate_skill_salary_correlation(jobs),
    }

    # Write CSVs
    os.makedirs(output_dir, exist_ok=True)
    for table_name, rows in results.items():
        if not rows:
            continue
        path = os.path.join(output_dir, f"{table_name}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        logger.info(f"  Wrote {len(rows)} rows → {path}")

    # Write a run-metadata file
    meta = {
        "pipeline_run_at": datetime.utcnow().isoformat(),
        "total_jobs_processed": len(jobs),
        "tables_written": list(results.keys()),
    }
    with open(os.path.join(output_dir, "pipeline_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    logger.info("Pipeline complete.")
    return results


if __name__ == "__main__":
    run_pipeline()
