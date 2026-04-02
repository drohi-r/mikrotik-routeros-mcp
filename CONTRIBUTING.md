# Contributing

## Current standards

- keep tools device-scoped
- prefer named, bounded tools over broad raw execution
- preserve the guarded write workflow
- avoid silent destructive behavior
- add tests for config parsing or safety logic when changing those areas

## Local development

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m compileall src tests
```

## Pull requests

- explain the operational impact on RouterOS devices
- note whether a change affects API, API-SSL, SSH, or configuration loading
- include validation steps in the PR description
