FROM python:3.11-slim

# Copy uv from official image
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cached layer)
COPY backend/pyproject.toml backend/uv.lock* ./backend/
RUN cd backend && uv sync --frozen --no-dev || cd backend && uv sync --no-dev

# Copy backend source
COPY backend ./backend

WORKDIR /app/backend

EXPOSE 5001

CMD ["uv", "run", "python", "run.py"]
