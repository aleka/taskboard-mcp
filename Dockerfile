FROM python:3.13-slim

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy project definition and install dependencies
COPY pyproject.toml .
RUN uv pip install --system --no-cache-dir .

# Copy application source
COPY taskboard/ taskboard/

# Database volume
ENV TASKBOARD_DB=/root/.taskboard/taskboard.db

EXPOSE 7438

CMD ["uvicorn", "taskboard.web.app:create_app", "--host", "0.0.0.0", "--port", "7438", "--factory"]
