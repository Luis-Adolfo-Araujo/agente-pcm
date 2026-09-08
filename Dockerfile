# A demonstração é um processo só: a API do agente serve, na própria raiz, a
# interface já exportada. Duas imagens intermediárias e uma final enxuta —
# Node não sobrevive ao build, e o runtime carrega apenas Python.

FROM node:20-alpine AS interface
WORKDIR /interface
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
# Vazio de propósito: a interface chama a API por caminho relativo, na mesma
# origem. Qualquer valor aqui viraria uma URL fixa dentro do bundle.
ENV NEXT_PUBLIC_API=""
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY config ./config
COPY demo ./demo
COPY --from=interface /interface/out ./web-dist

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    MAIA_WEB_DIR=/app/web-dist \
    MAIA_PILOT_SNAPSHOT_DIR=/app/demo/snapshots \
    MAIA_PILOT_RUN_DIR=/tmp/maia/runs \
    MAIA_PILOT_DB=/tmp/maia/pilot.sqlite3 \
    MAIA_PILOT_SHOW_RAW_WORKER_IDS=true \
    PORT=7860

# O Spaces publica na 7860; outros hosts injetam a porta em PORT.
EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn --factory api.app:create_app --host 0.0.0.0 --port ${PORT:-7860}"]
