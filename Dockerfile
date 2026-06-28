FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY dashboard_api.py gestion_tickets.py index.html style.css /app/

# #### VARIABLES D'ENVIRONNEMENT IMPORTANTES
# - REDIS_URL=redis://:motdepasse@redis:6379/0
# - ne pas utiliser APP_TICKET_DEFAULT_REDIS_URL sur ce dashboard
# - CAPACITE_SERVEUR=6
# - APPLICATIONS_TICKETS_JSON={...}

EXPOSE 8000

CMD ["sh", "-c", "uvicorn dashboard_api:app --host 0.0.0.0 --port ${PORT:-8000}"]
