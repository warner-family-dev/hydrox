FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/opt/hydrox

WORKDIR ${APP_HOME}

RUN apt-get update \
    && apt-get install -y --no-install-recommends git libraspberrypi-bin \
    && rm -rf /var/lib/apt/lists/* \
    && adduser --disabled-password --gecos '' appuser \
    && mkdir -p /data ${APP_HOME} \
    && chown -R appuser:appuser /data ${APP_HOME}

COPY requirements.txt ${APP_HOME}/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app ${APP_HOME}/app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
