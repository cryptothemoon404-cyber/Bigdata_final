"""
TechPulse TW - Job Listing Scraper
Scrapes job postings from 104.com.tw public API
"""

import requests
import json
import time
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# 104.com.tw public search API (no authentication required for public listings)
BASE_URL = "https://www.104.com.tw/jobs/search/api/jobs"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TechPulseTW/1.0; research)",
    "Referer": "https://www.104.com.tw/jobs/search/",
    "Accept": "application/json",
}

# Tech-related keyword queries to collect
QUERY_KEYWORDS = [
    "data engineer",
    "data scientist",
    "data analyst",
    "machine learning",
    "backend engineer",
    "frontend engineer",
    "DevOps",
    "cloud engineer",
    "software engineer",
    "AI engineer",
]

# Major tech hubs in Taiwan (region codes)
REGION_CODES = {
    "taipei": "6001001000",
    "new_taipei": "6001002000",
    "hsinchu": "6001017000",
    "taichung": "6001008000",
    "tainan": "6001020000",
    "kaohsiung": "6001005000",
}


def fetch_jobs(keyword: str, region: str = "6001001000", page: int = 1, rows: int = 20) -> Dict:
    """
    Fetch job listings from 104.com.tw search API.

    Args:
        keyword: Job title or skill keyword
        region: Geographic region code (default: Taipei)
        page: Page number
        rows: Results per page (max 20 for free tier)

    Returns:
        Parsed JSON response or empty dict on failure
    """
    params = {
        "keyword": keyword,
        "area": region,
        "order": "1",          # Sort by relevance
        "asc": "0",
        "s9": "1",             # Full-time only
        "page": page,
        "rows": rows,
        "mode": "s",
        "jobsource": "2018indexpoc",
    }

    try:
        resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.warning(f"Request failed for keyword='{keyword}' page={page}: {e}")
        return {}


def parse_job(raw: Dict) -> Optional[Dict]:
    """
    Normalize a raw job record from 104.com.tw into a flat schema.

    Returns None if the record is missing critical fields.
    """
    try:
        job_id = raw.get("jobNo") or raw.get("jobId")
        if not job_id:
            return None

        # Salary fields: salaryMin / salaryMax are monthly TWD; 0 means undisclosed
        salary_min = int(raw.get("salaryMin", 0) or 0)
        salary_max = int(raw.get("salaryMax", 0) or 0)

        # Skills / tags: comma-separated string in some API versions
        tags = raw.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        return {
            "job_id":       str(job_id),
            "title":        raw.get("jobName", ""),
            "company":      raw.get("custName", ""),
            "company_size": raw.get("coSize", ""),
            "location":     raw.get("jobAddrNoDesc", ""),
            "industry":     raw.get("industryDesc", ""),
            "salary_min":   salary_min,
            "salary_max":   salary_max,
            "salary_type":  raw.get("salaryDesc", ""),
            "experience":   raw.get("periodDesc", ""),
            "education":    raw.get("eduDesc", ""),
            "tags":         tags,
            "posted_date":  raw.get("appearDate", ""),
            "scraped_at":   datetime.utcnow().isoformat(),
            "url":          f"https://www.104.com.tw/job/ajax/content/{job_id}",
        }
    except Exception as e:
        logger.debug(f"Failed to parse job record: {e}")
        return None


def scrape_all(
    keywords: List[str] = QUERY_KEYWORDS,
    max_pages_per_keyword: int = 5,
    delay_seconds: float = 1.5,
    output_path: str = "data/jobs_raw.json",
) -> List[Dict]:
    """
    Full scrape run across all keywords and regions.

    Writes results to output_path as a JSON array and returns the list.
    Respects rate limits via delay_seconds between requests.
    """
    all_jobs: Dict[str, Dict] = {}   # Deduplicate by job_id

    for keyword in keywords:
        logger.info(f"Scraping keyword: '{keyword}'")
        for page in range(1, max_pages_per_keyword + 1):
            data = fetch_jobs(keyword, page=page)
            jobs_raw = data.get("data", {}).get("list", [])
            if not jobs_raw:
                logger.info(f"  No more results at page {page}, stopping.")
                break

            for raw in jobs_raw:
                parsed = parse_job(raw)
                if parsed and parsed["job_id"] not in all_jobs:
                    all_jobs[parsed["job_id"]] = parsed

            logger.info(f"  Page {page}: +{len(jobs_raw)} listings (total unique: {len(all_jobs)})")
            time.sleep(delay_seconds)

    result = list(all_jobs.values())

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info(f"Scrape complete. {len(result)} unique jobs saved to {output_path}")
    return result


if __name__ == "__main__":
    scrape_all()
