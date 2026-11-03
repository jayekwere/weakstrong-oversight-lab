# Security policy
Report a suspected vulnerability using [GitHub private vulnerability reporting](https://github.com/jayekwere/weakstrong-oversight-lab/security/advisories/new). Include a minimal synthetic reproduction and affected version; do not publish secrets or real-user records in an issue.

Version 0.1.x is the supported line. Security fixes receive a patch release. This is a local research application with synthetic resources; it is not a hosted multi-user security boundary or a validated safeguard for real agents. Review [the threat model](docs/threat-model.md) before adapting it.

External model calls are opt-in, with credentials read from environment variables. Never include credentials in configuration files, traces, prompts or bug reports. Keep the application on loopback. If using a reverse proxy, add authentication, TLS, request limits and an explicit trusted-host configuration; an optional LAB_API_TOKEN protects write requests but does not make result reads private.
