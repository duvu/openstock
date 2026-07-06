# Docker Runtime

Run the vnstock local data service in a Docker container for easy isolated deployment.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose v2 (optional, for compose workflow)

## Quick Start

### Build the image

```bash
docker build -t vnstock-service .
```

### Run the service

```bash
docker run -p 127.0.0.1:6900:6900 \
  -v ~/.config/vnstock:/home/vnstock/.config/vnstock:ro \
  vnstock-service
```

Test it:

```bash
curl http://127.0.0.1:6900/healthz
# {"status": "ok", "service": "vnstock"}
```

## Local-Only Default Binding

The `-p 127.0.0.1:6900:6900` flag publishes port 6900 **only on localhost**. This prevents accidental public internet exposure.

**Never use `-p 0.0.0.0:6900:6900` or `-p 6900:6900`** unless you have a firewall and understand the security implications. The service has no authentication for data endpoints and is not hardened for public access.

## Auth Credentials Volume

Credentials stored via `vnstock-auth login` live in `~/.config/vnstock/credentials/` on your host. Mount this directory to give the container access:

```bash
-v ~/.config/vnstock:/home/vnstock/.config/vnstock:ro
```

Use `:ro` (read-only) for the running service. For interactive login, mount with write access (see below).

## Interactive Login in Docker

Run the login command in a separate container **before** starting the service:

```bash
docker run -it --rm \
  -v ~/.config/vnstock:/home/vnstock/.config/vnstock \
  vnstock-service vnstock-auth login tcbs
```

This writes credentials to your host's `~/.config/vnstock/credentials/tcbs.json`. The service container then reads them via the `:ro` mount.

After login, restart or start the service:

```bash
docker run -p 127.0.0.1:6900:6900 \
  -v ~/.config/vnstock:/home/vnstock/.config/vnstock:ro \
  vnstock-service
```

## Docker Compose

Use the provided `docker-compose.yml` for a managed workflow:

```bash
# Start the service
docker compose up -d

# Check status
docker compose ps
curl http://127.0.0.1:6900/healthz

# Interactive login (one-shot)
docker compose run --rm vnstock-login vnstock-auth login tcbs

# Stop
docker compose down
```

## Healthcheck

The Docker image includes a built-in healthcheck:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:6900/healthz')" || exit 1
```

Check container health:

```bash
docker inspect --format='{{.State.Health.Status}}' vnstock-service
```

## Single-User Local Scope

This Docker setup is designed for **single-user local use** only:

- Binds to `127.0.0.1` by default (localhost)
- No TLS, no HTTPS, no API auth
- Credentials are from your personal `~/.config/vnstock/` directory
- No multi-user session isolation

## Out of Scope: Public Internet Deployment

Deploying this service to a public server, cloud VM, or shared network is **out of scope** and **not supported**. The service:

- Has no HTTPS/TLS
- Has no authentication for data endpoints
- Has no rate limiting
- Is designed only for local development and personal data workflows

If you need a production data API, use the provider APIs directly or build a properly secured wrapper.
