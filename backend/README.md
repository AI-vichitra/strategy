# StratAI Backend

Python FastAPI backend for the StratAI strategy generation platform.

## Setup

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Run dev server
uvicorn main:app --reload --port 8000
```

## Structure

```
backend/
├── main.py          # FastAPI app entry point
├── requirements.txt
├── routers/         # Route handlers
├── services/        # Business logic / AI calls
└── models/          # Pydantic data models
```

API will be available at http://localhost:8000
Interactive docs at http://localhost:8000/docs
