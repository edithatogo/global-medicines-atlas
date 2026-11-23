FROM ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 AS uv
FROM python:3.15.1-bookworm@sha256:2734c1683bd937b316f31b18972026302f155f0ffd932b329811d2e3a8450775 AS build
COPY --from=uv /uv /usr/local/bin/uv
RUN python -c 'import platform; assert platform.python_version() == "3.15.1"'
WORKDIR /app
COPY cacert.pem .
ENV SSL_CERT_FILE=/app/cacert.pem
COPY requirements.txt .
RUN uv pip install --system --require-hashes -r requirements.txt
COPY *.whl ./
RUN uv pip install --system --no-deps ./*.whl

FROM python:3.15.1-slim-bookworm@sha256:575f8bc12ec26542e0678bc6b60e385218248019d433157ec327264a78c3a853
COPY --from=build /usr/local/lib/python3.15/site-packages /usr/local/lib/python3.15/site-packages
COPY --from=build /app/cacert.pem /app/cacert.pem
WORKDIR /app
RUN useradd --create-home --uid 1000 app
USER app
ENV PYTHONUNBUFFERED=1 SSL_CERT_FILE=/app/cacert.pem
EXPOSE 7860
CMD ["python", "-m", "uvicorn", "global_medicines_atlas.hosted_service:create_app", "--factory", "--host", "0.0.0.0", "--port", "7860"]
