# Gemini CLI in Dev Container

This project uses the Gemini CLI for assistance. It is automatically installed in the development container.

## Authentication

When running in a development container, you must use the `NO_BROWSER=true` flag for authentication:

```bash
NO_BROWSER=true gemini auth login
```

Follow the link provided in the terminal to authorize the application with your Google account, and then copy the authorization code back into the terminal.

## Project Overview

This repository contains `finance-aggregator`, a service that integrates with open banking (via TrueLayer) to aggregate financial data (accounts, transactions).

### Architecture

The project is split into several main components:
- **`api/`**: A FastAPI application that serves the REST API.
- **`sync_worker/`**: A background job (designed to run as a Cloud Run Job) that periodically synchronizes accounts and transactions.
- **`app/`**: The core application library shared by both the API and the worker:
  - **`adapters/`**: Bank-specific data normalizers (Amex, Chase, Monzo, Natwest) for standardizing transaction data received from TrueLayer.
  - **`models/`**: SQLAlchemy ORM models (Account, Transaction, Token).
  - **`schemas/`**: Pydantic models for API request/response validation.
  - **`services/`**: Core business logic (account management, transaction processing, TrueLayer API integration).
- **`deploy/`**: Google Cloud Platform deployment configurations (Cloud Run, Cloud Build).
- **`alembic/`**: Database migrations.

### Tech Stack

- **Language:** Python 3.13
- **Package Manager:** `uv`
- **Web Framework:** FastAPI
- **Database ORM:** SQLAlchemy (asyncio) + Alembic
- **Database:** PostgreSQL (with asyncpg)
- **External Integrations:** TrueLayer API
- **Testing:** `pytest`, `pytest-asyncio`, `respx` (HTTP mocking), `testcontainers` (PostgreSQL)
- **Linting & Formatting:** `ruff`
- **Type Checking:** `mypy`
- **Deployment:** Docker, Google Cloud Run, Google Cloud Build
