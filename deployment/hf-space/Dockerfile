FROM ghcr.io/astral-sh/uv:0.13.6 AS uv
FROM python:3.15.1-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
RUN python -c 'import platform; assert platform.python_version() == "3.15.1"'
WORKDIR /app
COPY cacert.pem .
ENV SSL_CERT_FILE=/app/cacert.pem
COPY requirements.txt .
RUN uv pip install --system --require-hashes -r requirements.txt
COPY *.whl ./
RUN uv pip install --system --no-deps ./*.whl
RUN useradd --create-home --uid 1000 app
USER app
ENV PYTHONUNBUFFERED=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1
EXPOSE 7860
CMD ["python", "-m", "uvicorn", "global_medicines_atlas.hosted_service:create_app", "--factory", "--host", "0.0.0.0", "--port", "7860"]
