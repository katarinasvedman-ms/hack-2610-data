FROM node:24.21.0-alpine3.23 AS frontend-build
WORKDIR /work/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000
WORKDIR /app
COPY backend/ ./backend/
COPY knowledge/ ./knowledge/
COPY --from=frontend-build /work/frontend/dist ./frontend/dist/
RUN pip install --no-cache-dir -r backend/requirements.txt
RUN addgroup --system app && adduser --system --ingroup app --no-create-home app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--app-dir", "/app/backend", "--host", "0.0.0.0", "--port", "8000"]
