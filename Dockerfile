# Playwright base image ships Chromium preinstalled — reused for both scraping and
# PDF rendering, so no extra system deps are needed.
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# migrate + collectstatic at startup, then serve via gunicorn.
CMD python manage.py migrate --noinput && \
    python manage.py collectstatic --noinput && \
    gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
