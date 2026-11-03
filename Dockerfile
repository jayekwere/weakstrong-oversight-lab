FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/app/src
WORKDIR /app
RUN groupadd --gid 10001 lab && useradd --uid 10001 --gid lab --no-create-home lab
COPY requirements.lock /app/requirements.lock
RUN python -m pip install --require-hashes -r requirements.lock
COPY pyproject.toml README.md LICENSE /app/
COPY src /app/src
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["python", "-m", "weakstrong.cli"]
CMD ["serve"]
