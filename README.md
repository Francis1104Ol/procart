# ProCart

A modern payment-first e-commerce platform.

## CAT-001: Service Foundation

This ticket establishes the initial service foundation for ProCart.

### Stack

- **FastAPI** — API service
- **PostgreSQL** — Relational database
- **SQLAlchemy** — Database access
- **Alembic** — Database migrations
- **Docker Compose** — Local development environment
- **pytest** — Automated tests

### Requirements

Ensure you have the following installed:
- Git
- Docker Desktop

---

### Start the Service

1. **Clone the repository and navigate to the directory:**
   ```bash
   git clone https://github.com/Francis1104OI/procart.git
   cd procart
   ```

2. **Build and start the service:**
   ```bash
   docker compose up --build
   ```

The API will be available at: `http://localhost:8000`

> **Note:** Keep this terminal running while testing the API.

---

### Verify the Service

Open a second terminal to verify the endpoints.

#### Health Check
Send a request to the health endpoint:
```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "ok"
}
```

#### Unsupported Endpoint
An unsupported endpoint returns a clear error instead of an empty success:
```bash
curl http://localhost:8000/payments
```

**Expected response:**
```json
{
  "error": "not_found",
  "message": "The endpoint '/payments' is not available."
}
```

#### Interactive Documentation
Interactive API documentation is available at: `http://localhost:8000/docs`

---

### Run Tests Locally

1. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   ```

2. **Activate the virtual environment:**
   - **Windows PowerShell:**
     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```
   - **macOS / Linux:**
     ```bash
     source .venv/bin/activate
     ```

3. **Install the development dependencies:**
   ```bash
   python -m pip install -e ".[dev]"
   ```

4. **Run the tests:**
   ```bash
   python -m pytest
   ```

The **CAT-001** test suite covers:
- Successful health check execution.
- Unsupported endpoint routing (returning a clear 404 response).

---
## CAT-002: Seed the Catalogue

CAT-002 provides a deterministic large-scale product catalogue used for search, filtering, and pagination testing.

Start the Docker environment:

```powershell
docker compose up -d --build
```

Seed the catalogue with 500,000 products:

```powershell
docker compose exec api python -m app.seed.catalogue --count 500000 --seed 20260911
```

A successful seed reports:

- requested product count
- actual product count
- seed value
- dataset checksum
- generation time

Re-running the command replaces the existing catalogue rather than appending duplicate products. The default seed is deterministic and is verified against a known baseline checksum.

Detailed measurements and dataset distributions are recorded in `docs/seed-results.md`.
### Architecture Decisions

The service, database, and API decisions are documented in: `docs/architecture-decision.md`
