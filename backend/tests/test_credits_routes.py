from app.main import app


def test_credit_endpoints_are_registered():
    paths = {
        route.path
        for route in app.routes
        if getattr(route, "methods", None) and "GET" in route.methods
    }

    assert "/api/v1/credits/balance" in paths
    assert "/api/v1/credits/transactions" in paths


def test_google_play_purchase_verification_route_is_registered():
    routes = {
        (route.path, method)
        for route in app.routes
        if getattr(route, "methods", None)
        for method in route.methods
    }

    assert ("/api/v1/credits/google-play/verify", "POST") in routes
