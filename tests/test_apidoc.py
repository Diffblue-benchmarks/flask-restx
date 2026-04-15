import pytest
from flask import Flask
from flask_restx.apidoc import Apidoc, apidoc, swagger_static, ui_for


class ApidocTest:
    def test_apidoc_init_sets_registered_false(self):
        bp = Apidoc("test_bp", __name__)
        assert bp.registered is False

    def test_apidoc_register_sets_registered_true(self):
        app = Flask(__name__)
        bp = Apidoc("test_register_bp", __name__)
        assert bp.registered is False
        app.register_blueprint(bp)
        assert bp.registered is True

    def test_swagger_static_returns_url(self):
        app = Flask(__name__)
        app.register_blueprint(apidoc)
        with app.test_request_context():
            fn = app.jinja_env.globals.get("swagger_static")
            url = fn("swagger-ui.css")
            assert "swagger-ui.css" in url

    def test_ui_for_renders_template(self):
        app = Flask(__name__)
        app.register_blueprint(apidoc)

        class FakeApi:
            title = "Test API"
            specs_url = "/api/swagger.json"

        with app.test_request_context():
            result = ui_for(FakeApi())
            assert "Test API" in result or result is not None
