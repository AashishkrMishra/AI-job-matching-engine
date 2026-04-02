# AI Job Tracker

A full-stack AI-powered job application tracker with resume analysis, skill matching, and personalized recommendations.

## Tech Stack

| Layer     | Technology                              |
| --------- | --------------------------------------- |
| Backend   | FastAPI, SQLAlchemy, PostgreSQL          |
| Frontend  | React 19, Vite, React Router            |
| AI/NLP    | spaCy, scikit-learn, HuggingFace API    |
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

# Download spaCy model
python -m spacy download en_core_web_sm

# Configure environment
cp .env.example .env
# Edit .env with your actual DATABASE_URL and HF_API_TOKEN

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

| Variable       | Description                        |
| -------------- | ---------------------------------- |
| `DATABASE_URL` | PostgreSQL connection string       |
| `HF_API_TOKEN` | HuggingFace API token              |

See [`.env.example`](.env.example) for the template.

## API Endpoints

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

## Project Structure

```
AI_BACKEND/
├── app/
│   ├── ai/                  # AI/NLP modules
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
├── frontend/                # React + Vite app
│   ├── src/
│   │   └── pages/
│   └── package.json
├── .env.example             # Environment template
├── .gitignore
├── requirements.txt
└── README.md
```

## License

This project is for personal/educational use.
