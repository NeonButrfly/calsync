FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY alembic.ini ./
COPY alembic ./alembic

RUN pip install --upgrade pip && pip install .

CMD ["python", "-m", "uvicorn", "calsync.main:app", "--host", "0.0.0.0", "--port", "3080"]
