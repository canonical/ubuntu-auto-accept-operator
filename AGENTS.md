# Agent Instructions

## Running Tests

Always use `make unit` to run unit tests. Do not use `pip`, `pytest`, or `uv` directly.

```
make unit
```

## Linting and Formatting

Use `make format` to auto-fix linting and formatting issues (preferred over `make lint`, which only checks without fixing):

```
make format
```

If you only want to check without fixing, use:

```
make lint
```

## Workflow

After making code changes, and before proposing or presenting them, always:
1. Run `make format` to fix any style issues.
2. Run `make unit` to verify tests pass.

## Dependency Files

Use the Makefile targets instead of calling `uv` directly when updating project dependencies:

1. Run `make update-dependencies` to refresh `uv.lock`.
2. Run `make generate-requirements` to regenerate `requirements.txt` and `requirements-dev.txt`.
