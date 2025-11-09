# Fintrid Backend API

A complete Python backend solution with FastAPI and Streamlit UI for the Fintrid financial application.

## API Endpoints

### Health Check
- `GET /` - Root endpoint with health status
- `GET /api/health` - Health check endpoint

## Setup Instructions

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv .venv
   ```

3. **Activate the virtual environment:**
   - Windows:
     ```bash
     .venv\Scripts\activate
     ```
   - macOS/Linux:
     ```bash
     source .venv/bin/activate
     ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Running the Application

### 1. Start the FastAPI Backend

```bash
uv run fintrid-api
```

The API will be available at:
- **API Base URL:** http://localhost:8000
- **Swagger UI (Interactive Docs):** http://localhost:8000/docs
- **ReDoc (Alternative Docs):** http://localhost:8000/redoc

### 2. Start the Streamlit UI (in a new terminal)

```bash
uv run python run_ui.py
```

Or directly with streamlit:
```bash
uv run streamlit run src/fintrid_backend/streamlit_app.py
```

The Streamlit UI will be available at:
- **Streamlit UI:** http://localhost:8501