# Security Policy

## Scope

This project can interact with production MikroTik RouterOS devices. Treat it as operational infrastructure code, not a toy demo.

## Supported versions

Only the latest `main` branch state is supported at this stage.

## Reporting a vulnerability

Do not open public issues for credential leaks, unsafe write behavior, auth bypasses, or transport-layer vulnerabilities.

Report security concerns privately to:

- `info@ecube-entertainment.com`

Include:

- affected version or commit
- reproduction steps
- impact on RouterOS devices or credentials
- whether the issue requires API, API-SSL, or SSH access

## Operational guidance

- use read-only mode by default
- keep `allow_writes: false` unless you explicitly need write access
- prefer per-device least privilege accounts
- do not commit real `devices.yaml` files or router credentials
