from datetime import timedelta

import pytest
from flask import Flask


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


def test_crossdomain_basic_get_request(app):
    from flask_restx.cors import crossdomain

    @app.route("/test")
    @crossdomain(origin="*")
    def test_view():
        return "ok"

    with app.test_client() as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        assert resp.headers["Access-Control-Allow-Origin"] == "*"


def test_crossdomain_options_request_automatic(app):
    from flask_restx.cors import crossdomain

    @app.route("/test", methods=["GET", "OPTIONS"])
    @crossdomain(origin="*")
    def test_view():
        return "ok"

    with app.test_client() as client:
        resp = client.options("/test")
        assert resp.headers["Access-Control-Allow-Origin"] == "*"


def test_crossdomain_methods_list(app):
    from flask_restx.cors import crossdomain

    @app.route("/test")
    @crossdomain(origin="*", methods=["get", "post"])
    def test_view():
        return "ok"

    with app.test_client() as client:
        resp = client.get("/test")
        assert "GET" in resp.headers["Access-Control-Allow-Methods"]
        assert "POST" in resp.headers["Access-Control-Allow-Methods"]


def test_crossdomain_headers_list(app):
    from flask_restx.cors import crossdomain

    @app.route("/test")
    @crossdomain(origin="*", headers=["content-type", "authorization"])
    def test_view():
        return "ok"

    with app.test_client() as client:
        resp = client.get("/test")
        assert "CONTENT-TYPE" in resp.headers["Access-Control-Allow-Headers"]
        assert "AUTHORIZATION" in resp.headers["Access-Control-Allow-Headers"]


def test_crossdomain_headers_string(app):
    from flask_restx.cors import crossdomain

    @app.route("/test")
    @crossdomain(origin="*", headers="Content-Type")
    def test_view():
        return "ok"

    with app.test_client() as client:
        resp = client.get("/test")
        assert resp.headers["Access-Control-Allow-Headers"] == "Content-Type"


def test_crossdomain_expose_headers_list(app):
    from flask_restx.cors import crossdomain

    @app.route("/test")
    @crossdomain(origin="*", expose_headers=["x-custom", "x-other"])
    def test_view():
        return "ok"

    with app.test_client() as client:
        resp = client.get("/test")
        assert "X-CUSTOM" in resp.headers["Access-Control-Expose-Headers"]
        assert "X-OTHER" in resp.headers["Access-Control-Expose-Headers"]


def test_crossdomain_expose_headers_string(app):
    from flask_restx.cors import crossdomain

    @app.route("/test")
    @crossdomain(origin="*", expose_headers="X-Custom")
    def test_view():
        return "ok"

    with app.test_client() as client:
        resp = client.get("/test")
        assert resp.headers["Access-Control-Expose-Headers"] == "X-Custom"


def test_crossdomain_origin_list(app):
    from flask_restx.cors import crossdomain

    @app.route("/test")
    @crossdomain(origin=["http://example.com", "http://other.com"])
    def test_view():
        return "ok"

    with app.test_client() as client:
        resp = client.get("/test")
        assert "http://example.com" in resp.headers["Access-Control-Allow-Origin"]
        assert "http://other.com" in resp.headers["Access-Control-Allow-Origin"]


def test_crossdomain_max_age_timedelta(app):
    from flask_restx.cors import crossdomain

    @app.route("/test")
    @crossdomain(origin="*", max_age=timedelta(hours=1))
    def test_view():
        return "ok"

    with app.test_client() as client:
        resp = client.get("/test")
        assert resp.headers["Access-Control-Max-Age"] == "3600.0"


def test_crossdomain_max_age_int(app):
    from flask_restx.cors import crossdomain

    @app.route("/test")
    @crossdomain(origin="*", max_age=600)
    def test_view():
        return "ok"

    with app.test_client() as client:
        resp = client.get("/test")
        assert resp.headers["Access-Control-Max-Age"] == "600"


def test_crossdomain_credentials(app):
    from flask_restx.cors import crossdomain

    @app.route("/test")
    @crossdomain(origin="*", credentials=True)
    def test_view():
        return "ok"

    with app.test_client() as client:
        resp = client.get("/test")
        assert resp.headers["Access-Control-Allow-Credentials"] == "true"


def test_crossdomain_no_credentials(app):
    from flask_restx.cors import crossdomain

    @app.route("/test")
    @crossdomain(origin="*", credentials=False)
    def test_view():
        return "ok"

    with app.test_client() as client:
        resp = client.get("/test")
        assert "Access-Control-Allow-Credentials" not in resp.headers


def test_crossdomain_attach_to_all_false_non_options(app):
    from flask_restx.cors import crossdomain

    @app.route("/test")
    @crossdomain(origin="*", attach_to_all=False)
    def test_view():
        return "ok"

    with app.test_client() as client:
        resp = client.get("/test")
        assert "Access-Control-Allow-Origin" not in resp.headers


def test_crossdomain_attach_to_all_false_options(app):
    from flask_restx.cors import crossdomain

    @app.route("/test", methods=["GET", "OPTIONS"])
    @crossdomain(origin="*", attach_to_all=False)
    def test_view():
        return "ok"

    with app.test_client() as client:
        resp = client.options("/test")
        assert resp.headers["Access-Control-Allow-Origin"] == "*"


def test_crossdomain_automatic_options_false(app):
    from flask_restx.cors import crossdomain

    @app.route("/test", methods=["GET", "OPTIONS"])
    @crossdomain(origin="*", automatic_options=False)
    def test_view():
        return "ok"

    with app.test_client() as client:
        resp = client.options("/test")
        assert resp.headers["Access-Control-Allow-Origin"] == "*"


def test_crossdomain_get_methods_from_app(app):
    from flask_restx.cors import crossdomain

    @app.route("/test", methods=["GET", "OPTIONS"])
    @crossdomain(origin="*", methods=None)
    def test_view():
        return "ok"

    with app.test_client() as client:
        resp = client.get("/test")
        assert "Access-Control-Allow-Methods" in resp.headers


def test_crossdomain_preserves_function_name(app):
    from flask_restx.cors import crossdomain

    @crossdomain(origin="*")
    def my_view():
        return "ok"

    assert my_view.__name__ == "my_view"
