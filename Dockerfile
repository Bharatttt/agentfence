FROM python:3.12-slim
WORKDIR /app
COPY requirements-runtime.txt .
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked python -m pip install --timeout 180 --retries 10 --disable-pip-version-check pip==26.2.1
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked python -m pip install --timeout 180 --retries 10 --disable-pip-version-check --resume-retries 10 -r requirements-runtime.txt
RUN useradd --uid 10001 --create-home agentfence
COPY agentfence ./agentfence
RUN mkdir -p /app/runtime/state && chown -R 10001:10001 /app/runtime
USER 10001:10001
EXPOSE 8000
CMD ["python","-m","uvicorn","agentfence.app:create_app","--factory","--host","0.0.0.0","--port","8000","--no-access-log"]
