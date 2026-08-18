FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN useradd -m -u 1000 user

USER user

ENV HOME=/home/user \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/user/app/.venv/bin:$PATH"

WORKDIR /home/user/app

COPY --chown=user:user pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=user:user main.py ./

EXPOSE 7860

CMD ["/home/user/app/.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]