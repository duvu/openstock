# vnstock Local Data Service - Docker Runtime
#
# Single-user, localhost-only deployment.
# Public internet exposure is NOT supported and out of scope.
#
# Build:
#   docker build -t vnstock-service .
#
# Run:
#   docker run -p 127.0.0.1:6900:6900 \
#     -v ~/.config/vnstock:/home/vnstock/.config/vnstock:ro \
#     vnstock-service
#
# Interactive login (run before the service, or in a separate terminal):
#   docker run -it --rm \
#     -v ~/.config/vnstock:/home/vnstock/.config/vnstock \
#     vnstock-service vnstock-auth login tcbs

FROM python:3.11-slim

# Non-root user for security
RUN useradd --create-home --shell /bin/bash vnstock

WORKDIR /app

# Install package
COPY pyproject.toml ./
COPY vnstock/ ./vnstock/
RUN pip install --no-cache-dir -e .

ARG INSTALL_FIINQUANTX=false
RUN if [ "$INSTALL_FIINQUANTX" = "true" ]; then \
      pip install --no-cache-dir matplotlib && \
      pip install --no-cache-dir \
        --extra-index-url https://fiinquant.github.io/fiinquantx/simple \
        fiinquantx==0.1.64; \
    fi

# Switch to non-root user
USER vnstock

# Config directory (mount for auth credentials)
RUN mkdir -p /home/vnstock/.config/vnstock

# Expose service port (localhost binding enforced by run command)
EXPOSE 6900

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:6900/healthz')" || exit 1

# Default: start local data service bound to all interfaces inside container
# The published port (-p) maps to localhost on the host
CMD ["vnstock-serve", "--host", "0.0.0.0", "--port", "6900"]
