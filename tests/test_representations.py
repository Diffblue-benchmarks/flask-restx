import json
import pytest
from flask import Flask
from flask_restx.representations import output_json


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


def test_output_json_basic(app):
    with app.app_context():
        data = {"key": "value"}
        resp = output_json(data, 200)
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert json.loads(body.strip()) == data
        assert body.endswith("\n")


def test_output_json_with_headers(app):
    with app.app_context():
        data = {"key": "value"}
        resp = output_json(data, 201, headers={"X-Custom": "header"})
        assert resp.status_code == 201
        assert resp.headers["X-Custom"] == "header"


def test_output_json_no_headers(app):
    with app.app_context():
        data = [1, 2, 3]
        resp = output_json(data, 200)
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert json.loads(body.strip()) == [1, 2, 3]


def test_output_json_debug_mode_sets_indent(app):
    app.debug = True
    with app.app_context():
        data = {"key": "value"}
        resp = output_json(data, 200)
        body = resp.get_data(as_text=True)
        assert "    " in body


def test_output_json_debug_mode_does_not_override_indent(app):
    app.debug = True
    app.config["RESTX_JSON"] = {"indent": 2}
    with app.app_context():
        data = {"key": "value"}
        resp = output_json(data, 200)
        body = resp.get_data(as_text=True)
        assert "  " in body
        assert "    " not in body.replace("  ", "")


def test_output_json_uses_restx_json_config(app):
    app.config["RESTX_JSON"] = {"sort_keys": True}
    with app.app_context():
        data = {"b": 2, "a": 1}
        resp = output_json(data, 200)
        body = resp.get_data(as_text=True)
        parsed = json.loads(body.strip())
        assert list(parsed.keys()) == ["a", "b"]


def test_output_json_empty_data(app):
    with app.app_context():
        resp = output_json({}, 204)
        assert resp.status_code == 204
        body = resp.get_data(as_text=True)
        assert json.loads(body.strip()) == {}
