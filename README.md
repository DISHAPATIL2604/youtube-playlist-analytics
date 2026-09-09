# 📊 YouTube Playlist Analytics

A production-ready web application that analyzes any public YouTube playlist and displays a YouTube Studio-style dark analytics dashboard.

**Stack**: Streamlit · FastAPI · PostgreSQL · YouTube Data API v3 · SQLAlchemy · Pydantic · Plotly

---

## 📸 Features

- **Playlist Input** — Enter any public YouTube Playlist URL
- **KPI Overview** — Total/Avg Views, Likes, Comments, Engagement Rate
- **Trend Analytics** — 5 interactive Plotly charts (Views, Likes, Comments trends; scatter plots)
- **Top Content** — Top 10 Most Viewed / Liked / Commented videos with thumbnails
- **Video Table** — Searchable/sortable table with all metrics + CSV export
- **No Duplicates** — Re-analyzing updates existing records safely
- **Refresh Button** — Pull latest YouTube stats anytime

---

## 🗂️ Project Structure

```
youtube-playlist-analytics/
├── backend/
│   ├── __init__.py
│   ├── main.py             # FastAPI app
│   ├── config.py           # Pydantic settings (reads .env)
│   ├── database.py         # SQLAlchemy engine & session
│   ├── models.py           # ORM models (Playlist, Video)
│   ├── schemas.py          # Pydantic request/response schemas
│   ├── crud.py             # DB CRUD with upsert logic
│   ├── youtube_service.py  # YouTube API integration
│   └── routes/
│       ├── __init__.py
│       └── playlist.py     # API route handlers
├── frontend/
│   └── app.py              # Streamlit dashboard
├── tests/
│   ├── __init__.py
│   ├── test_utils.py       # URL extraction & metrics
│   ├── test_crud.py        # DB CRUD (SQLite in-memory)
│   └── test_api.py         # FastAPI integration tests
├── .env                    # Your secrets (never commit!)
├── .env.example            # Template
├── .gitignore
├── requirements.txt
├── docker-compose.yml
└── README.md
```

---

## 🚀 Setup & Installation

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ (local or Docker)
- A YouTube Data API v3 key ([get one here](https://console.cloud.google.com/apis/credentials))

---

### 1. Get a YouTube Data API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Enable **YouTube Data API v3** under APIs & Services → Library
4. Create credentials → **API Key**
5. Copy the key — you'll add it to `.env` next

---

### 2. Configure Environment Variables

```bash
# Copy the example and edit it
copy .env.example .env
```

Edit `.env`:

```env
YOUTUBE_API_KEY=AIzaSy...your_real_key_here...

DATABASE_URL=postgresql://postgres:disha@localhost:5432/youtube_analytics
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=youtube_analytics
POSTGRES_USER=postgres
POSTGRES_PASSWORD=disha

BACKEND_URL=http://localhost:8000
```

---

### 3. Set Up PostgreSQL

#### Option A — Docker (recommended)

```bash
# Start only the database
docker compose up postgres -d

# Verify it's running
docker ps
```

#### Option B — Local PostgreSQL

```sql
-- Run in psql as superuser
CREATE DATABASE youtube_analytics;
-- User 'postgres' with password 'disha' should already exist,
-- otherwise run:
CREATE USER postgres WITH PASSWORD 'disha';
GRANT ALL PRIVILEGES ON DATABASE youtube_analytics TO postgres;
```

---

### 4. Install Python Dependencies

```bash
# Create a virtual environment (recommended)
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install all packages
pip install -r requirements.txt
```

---

### 5. Start the FastAPI Backend

```bash
# From the project root
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health check: [http://localhost:8000/health](http://localhost:8000/health)

Database tables are created automatically on first startup.

---

### 6. Start the Streamlit Frontend

```bash
# In a separate terminal (with venv activated)
streamlit run frontend/app.py --server.port 8501
```

- Dashboard: [http://localhost:8501](http://localhost:8501)

---

### 7. Run Tests

```bash
pytest tests/ -v
```

Tests use SQLite in-memory DB and mocked YouTube API — **no real API key or PostgreSQL needed**.

---

## 🐳 Full Docker Setup

```bash
# Add your API key to .env first, then:
docker compose up --build
```

Services:
| Service  | Port  | URL                      |
|----------|-------|--------------------------|
| postgres | 5432  | —                        |
| backend  | 8000  | http://localhost:8000    |
| frontend | 8501  | http://localhost:8501    |

---

## 📡 API Reference

| Method | Endpoint                        | Description                        |
|--------|---------------------------------|------------------------------------|
| GET    | `/health`                       | Health check (API + DB status)     |
| POST   | `/playlist/analyze`             | Fetch + store + return analytics   |
| GET    | `/playlist/{playlist_id}`       | Get stored playlist metadata       |
| GET    | `/playlist/{playlist_id}/videos`| Get all stored videos + metrics    |

### POST `/playlist/analyze` Request Body

```json
{
  "playlist_url": "https://www.youtube.com/playlist?list=PLxxxxxxxxxx"
}
```

---

## 📊 Metrics Definitions

| Metric          | Formula                                   |
|-----------------|-------------------------------------------|
| Like Rate       | `(likes / views) × 100`                  |
| Comment Rate    | `(comments / views) × 100`               |
| Engagement Rate | `((likes + comments) / views) × 100`     |

All metrics return `0.0` safely when `views == 0`.

---

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| `Cannot connect to backend` | Make sure FastAPI is running on port 8000 |
| `YOUTUBE_API_KEY not configured` | Add your key to `.env` |
| `Quota exceeded` | YouTube API has 10,000 units/day free quota |
| `Playlist not found` | Check the playlist is public and the URL is correct |
| `Database error` | Verify PostgreSQL is running and `.env` credentials match |

---

## 🏗️ Architecture

```
User (Browser)
    │
    ▼
Streamlit :8501  ──HTTP──▶  FastAPI :8000
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
            YouTube Data API v3       PostgreSQL :5432
            (fetch & validate)    (store & aggregate)
```

---

## 📝 License

MIT License — free to use and modify.

## Screen Recording Link (demo)
https://drive.google.com/file/d/1FyvDXnnO1nvWvUjQ8weLnQveNz0y4ffn/view?usp=drivesdk
