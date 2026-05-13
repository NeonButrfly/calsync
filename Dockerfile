FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY README.md pyproject.toml ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir .

EXPOSE 3080

CMD ["python", "-m", "uvicorn", "calsync.main:app", "--host", "0.0.0.0", "--port", "3080"]
