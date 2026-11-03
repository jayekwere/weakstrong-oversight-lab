# Architecture
    WeakStrong Oversight Lab is a single Python package with a local FastAPI application and a buildless, dependency-free browser dashboard. The CLI and API call the same research engine. Pydantic validates boundaries; model adapters accept observations and output schemas, never evaluator labels.

    ```mermaid
    flowchart LR
      CLI --> Engine
      Dashboard --> API[Local FastAPI]
      API --> Engine
      Dataset --> Engine
      Engine --> Strategies
      Strategies --> Adapters[Deterministic or opt-in HTTP adapters]
      Engine --> Results[Validated JSON + provenance]
      Results --> Dashboard
    ```

    Runtime dependencies are FastAPI, Pydantic, HTTPX and Uvicorn. No database, shell execution or cloud provisioning is required. Result writes are atomic. The browser receives synthetic public benchmark observations, not environment variables. Optional remote integration stays in the CLI; the web API only executes bounded simulations. The application is designed for one local researcher, not an authenticated multi-user service.
