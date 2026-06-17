# TechPulse TW

**Taiwan Tech Job Market Intelligence Platform**  
Monetizes public job-listing data from 104.com.tw into actionable hiring insights for HR teams and talent acquisition leaders.

> GitHub: https://github.com/cryptothemoon404-cyber/Bigdata_final  
> Live Demo: (add URL after deployment)

---

## Architecture Overview

```
104.com.tw (public API)
        │
        ▼
┌──────────────┐     JSON      ┌────────────────────┐     CSV / DB
│   Scraper    │ ──────────── ▶│  Batch Processor   │ ────────────▶ PostgreSQL
│ (Python,     │               │  (pandas / Spark)  │
│  requests)   │               └────────────────────┘
└──────────────┘                                              │
                                                              ▼
                                                   ┌──────────────────┐
                                                   │  FastAPI Backend │
                                                   │  (REST API)      │
                                                   └──────────────────┘
                                                              │
                                                              ▼
                                                   ┌──────────────────┐
                                                   │  HTML Dashboard  │
                                                   │  (Chart.js)      │
                                                   └──────────────────┘
```

---

## Quick Start (Local)

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (optional, for PostgreSQL)

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the scraper

```bash
python -m scraper.scraper
# Outputs: data/jobs_raw.json
```

To test without hitting the live API, use the included sample data:

```bash
cp data/sample_jobs.json data/jobs_raw.json
```

### 3. Run the processing pipeline

```bash
python -m pipeline.processor
# Outputs: data/skill_demand.csv, data/salary_distribution.csv, etc.
```

### 4. Start the API server

```bash
uvicorn api.main:app --reload --port 8000
```

### 5. Open the dashboard

Navigate to [http://localhost:8000](http://localhost:8000) in your browser.

---

## Running with Docker Compose

```bash
docker-compose up --build
```

This starts PostgreSQL (port 5432) and the API server (port 8000).

---

## Project Structure

```
techpulse-tw/
├── scraper/
│   └── scraper.py          # Scrapes 104.com.tw job listings
├── pipeline/
│   └── processor.py        # Batch aggregation pipeline
├── api/
│   └── main.py             # FastAPI REST API
├── frontend/
│   └── index.html          # Single-page analytics dashboard
├── data/
│   └── sample_jobs.json    # Sample data for local testing
├── scripts/
│   └── setup_db.sql        # PostgreSQL schema
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Liveness check |
| GET | `/api/skills?top=20` | Top skill demand ranking |
| GET | `/api/salary-distribution` | Salary bucket distribution |
| GET | `/api/industries?top=15` | Top hiring industries |
| GET | `/api/companies?top=15` | Top hiring companies |
| GET | `/api/skill-salary?top=15` | Skills × avg salary |
| GET | `/api/summary` | Dashboard summary stats |

Full interactive docs available at `/docs` (Swagger UI).

---

## Data Ethics & Legal

- Only public job listing data (no login required) is scraped.
- Requests include proper `User-Agent` identification and respect rate limits (1.5 s delay between pages).
- No personal data (candidate profiles, resumes) is collected.
- Data is used for aggregate analytics only; individual job records are not re-published.

---

## Scaling Notes

At 10× volume (~500K jobs/month):
- Replace pandas processor with **Apache Spark** job on EMR / Dataproc.
- Use **Kafka** to stream new postings in real time.
- Switch CSV file output to **PostgreSQL UPSERT** via asyncpg.

At 100× volume (~5M jobs/month):
- Partition PostgreSQL by `posted_date` or migrate to **Redshift / BigQuery**.
- Add **Elasticsearch** for full-text job-description search.
- Deploy API behind a load balancer with horizontal pod autoscaling (Kubernetes).
