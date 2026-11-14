"""Independent evaluator services with explicit data contracts.

Each module is a pure, deterministic service boundary. The FastAPI application
currently hosts them in-process; the contracts are intentionally transport-neutral
so services can be split into deployable processes without changing the API contract.
"""
