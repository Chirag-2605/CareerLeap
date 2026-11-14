from app.main import app


def test_api_exposes_only_one_production_analysis_endpoint():
    paths = {
        route.path
        for route in app.routes
        if getattr(route, "methods", None) and "POST" in route.methods
    }

    assert "/api/v1/analyze" in paths
    assert not any(path.startswith("/api/v2/") for path in paths)
    assert not any(path.startswith("/api/v3/") for path in paths)
    assert not any(path.startswith("/api/v4/") for path in paths)
