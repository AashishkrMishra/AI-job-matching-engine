# AI Job Tracker

A full-stack AI-powered job application tracker with resume analysis, skill matching, and personalized recommendations.

## Tech Stack

| Layer     | Technology                              |
| --------- | --------------------------------------- |
| Backend   | FastAPI, SQLAlchemy, PostgreSQL          |
| Frontend  | React 19, Vite, React Router            |
| AI/NLP    | Rule-based skill matching, HuggingFace API |
| Auth      | JWT (python-jose), bcrypt               |

## Features

- **User Authentication** — Register/Login with JWT-based auth
- **Job Tracking** — CRUD operations for job applications with status management
- **AI Job Analysis** — Extract skills and insights from job descriptions using NLP
- **Resume Analysis** — Upload resume (PDF/DOCX/TXT) and compare against job requirements
- **AI Recommendations** — Get personalized improvement suggestions via HuggingFace LLM

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL

### Backend Setup

```bash
# Clone the repo
git clone https://github.com/<your-username>/AI-Job-Tracker.git
cd AI-Job-Tracker

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — DATABASE_URL and SECRET_KEY are required, and the app will
# refuse to start without them. Generate a key with:
#   python -c "import secrets; print(secrets.token_urlsafe(48))"

# Apply database migrations
alembic upgrade head

# Start the backend
uvicorn app.main:app --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Environment Variables

| Variable       | Required | Description                               |
| -------------- | -------- | ----------------------------------------- |
| `DATABASE_URL` | yes      | PostgreSQL connection string              |
| `SECRET_KEY`   | yes      | JWT signing key (auto-generated on Render)|
| `HF_API_TOKEN` | no       | HuggingFace API token                     |
| `FRONTEND_URL` | no       | Frontend URL for CORS (Vercel URL in prod)|

The app raises on startup if a required variable is missing — there is no
fallback signing key, since a default would be identical in every clone of this
repo and would let anyone forge a token for any account. Generate one with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

See [`.env.example`](.env.example) for the template.

## API Endpoints

All endpoints except `/register` and `/login` require an `Authorization: Bearer <token>` header.

| Method   | Endpoint               | Description                  |
| -------- | ---------------------- | ---------------------------- |
| `POST`   | `/register`            | Register a new user          |
| `POST`   | `/login`               | Login and get JWT token      |
| `GET`    | `/me`                  | Get current user info        |
| `POST`   | `/jobs`                | Create a job application     |
| `GET`    | `/jobs`                | List user's job applications |
| `PATCH`  | `/jobs/{id}`           | Update job status            |
| `DELETE` | `/jobs/{id}`           | Delete a job application     |
| `POST`   | `/analyze-job`         | Analyze a job description    |
| `POST`   | `/analyze-resume`      | Analyze resume text vs job   |
| `POST`   | `/analyze-resume-file` | Upload & analyze resume file |

`/analyze-resume-file` takes `resume` (PDF/DOCX/TXT, max 5 MB) and
`job_description` as multipart form fields.

The two resume endpoints return `match_percentage: null` when no skills could be
read out of the job description — that is distinct from a genuine `0`.

### Request validation

| Field                | Rule                                                    |
| -------------------- | ------------------------------------------------------- |
| `password` (register) | at least 8 characters, and at most 72 **bytes** once UTF-8 encoded |
| `company`, `role`     | non-blank after trimming                                |
| `status`              | one of `applied`, `interview`, `offered`, `rejected`     |
| `description`, `resume`, `job` | 1 byte to 1 MB of text                         |

Violations return `422` with the offending field named. The status list is
mirrored by `STATUS_OPTIONS` in the dashboard, and a test asserts the two agree.

The password limit is measured in bytes rather than characters because that is
what bcrypt truncates at. A character limit would admit a 40-character accented
password at 80 bytes, and any other password sharing its first 72 bytes would
then be accepted as the same one.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The suite runs against a throwaway SQLite database built by Alembic, so it also
verifies that the migrations and the models agree.

## Database Migrations

Schema is owned by Alembic, not `create_all`.

```bash
alembic upgrade head                              # apply
alembic revision --autogenerate -m "description"  # create after editing models
alembic check                                     # fail if models drift from migrations
```

The baseline revision skips tables that already exist, so it can be applied to a
database that predates Alembic — including one built by the `create_all()` this
project used previously. No `alembic stamp` step is needed. Later revisions
should not copy that pattern; it is there only because the baseline has to adopt
schema it did not create.

## Project Structure

```
AI_BACKEND/
├── app/
│   ├── ai/                  # Skill matching + LLM recommendations
│   │   ├── skills.py        # Shared vocabulary, extractor, comparator
│   │   ├── job_analyzer.py
│   │   ├── resume_analyzer.py
│   │   ├── llm_recommender.py
│   │   └── file_parser.py
│   ├── main.py              # FastAPI app & routes
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── database.py          # DB connection
│   ├── auth.py              # JWT token creation
│   ├── security.py          # Password hashing
│   ├── config.py            # Environment config
│   └── dependencies.py      # Auth dependencies
├── alembic/                 # Migrations
│   └── versions/
├── tests/
├── frontend/                # React + Vite app
│   ├── src/
│   │   └── pages/
│   ├── vercel.json          # Vercel SPA config
│   └── package.json
├── .env.example             # Environment template
├── .gitignore
├── alembic.ini
├── build.sh                 # Render build script
├── pytest.ini
├── render.yaml              # Render blueprint
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## License

This project is for personal/educational use.
