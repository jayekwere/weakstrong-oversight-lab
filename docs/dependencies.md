# Dependency and asset policy
The project is Apache-2.0. The dashboard uses original HTML, CSS, JavaScript, Unicode symbols and system fonts; there are no bundled third-party images, webfonts or JavaScript libraries. Screenshots capture the actual local application.

Runtime dependencies and transitive packages are hash-locked in requirements.lock; the development graph is in uv.lock. FastAPI and Pydantic use MIT; HTTPX and Uvicorn use BSD-3-Clause; Starlette uses BSD-3-Clause; other installed metadata is reviewed during release verification. Dependency licenses remain with their respective packages. The container uses the official Python image with Debian components under their upstream terms. The base image is pinned to an immutable manifest digest. GitHub Actions are pinned to immutable commits and updated by Dependabot.

No model weights or external datasets are redistributed. Researchers are responsible for licenses and terms of optional local models or provider access they configure. Scan results reflect the database at execution time. They do not establish absence of vulnerabilities.
