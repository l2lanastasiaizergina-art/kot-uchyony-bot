FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY data ./data
RUN pip install --no-cache-dir .

RUN useradd --create-home botuser && mkdir -p /app/var && chown -R botuser:botuser /app
USER botuser

CMD ["orthogame"]

