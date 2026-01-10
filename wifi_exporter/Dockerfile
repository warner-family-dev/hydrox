FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends iw \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/wifi-exporter

COPY app.py /opt/wifi-exporter/app.py

EXPOSE 9100

CMD ["python", "/opt/wifi-exporter/app.py"]
