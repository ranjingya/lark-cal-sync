FROM ghcr.io/astral-sh/uv:0.11.29 AS uv
FROM python:3.14-slim
COPY --from=uv /uv /uvx /bin/
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev
RUN useradd --uid 10001 --create-home app && mkdir /app/data && chown app:app /app/data
USER app
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "lark-cal-sync", "serve", "--host", "0.0.0.0"]
