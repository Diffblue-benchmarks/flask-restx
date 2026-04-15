# -*- coding: utf-8 -*-
import pytest
from flask import Flask
from unittest.mock import MagicMock, patch

from flask_restx import Api, Resource
from flask_restx.model import ModelBase
from flask_restx.utils import BaseResponse


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def api(app):
    return Api(app)


# Tests for Resource.__init__

def test_resource_init_sets_api(api):
    resource = Resource(api=api)
    assert resource.api is api


def test_resource_init_with_none_api():
    resource = Resource(api=None)
    assert resource.api is None


def test_resource_init_default_api():
    resource = Resource()
    assert resource.api is None


# Tests for Resource.dispatch_request

def test_dispatch_request_calls_get_method(app, api):
    class MyResource(Resource):
        def get(self):
            return {"message": "ok"}

    with app.test_request_context("/", method="GET"):
        resource = MyResource(api=api)
        resp = resource.dispatch_request()
        assert resp == {"message": "ok"}


def test_dispatch_request_head_falls_back_to_get(app, api):
    class MyResource(Resource):
        def get(self):
            return {"message": "head_ok"}

    with app.test_request_context("/", method="HEAD"):
        resource = MyResource(api=api)
        resp = resource.dispatch_request()
        assert resp == {"message": "head_ok"}


def test_dispatch_request_post_method(app, api):
    class MyResource(Resource):
        def post(self):
            return {"created": True}

    with app.test_request_context("/", method="POST"):
        resource = MyResource(api=api)
        resp = resource.dispatch_request()
        assert resp == {"created": True}


def test_dispatch_request_applies_decorators(app, api):
    calls = []

    def my_decorator(f):
        def wrapper(*args, **kwargs):
            calls.append("decorator")
            return f(*args, **kwargs)
        return wrapper

    class MyResource(Resource):
        method_decorators = [my_decorator]

        def get(self):
            return {"ok": True}

    with app.test_request_context("/", method="GET"):
        resource = MyResource(api=api)
        resource.dispatch_request()
        assert "decorator" in calls


def test_dispatch_request_returns_base_response(app, api):
    from flask import Response

    class MyResource(Resource):
        def get(self):
            return Response("direct", status=200)

    with app.test_request_context("/", method="GET"):
        resource = MyResource(api=api)
        resp = resource.dispatch_request()
        assert isinstance(resp, BaseResponse)


def test_dispatch_request_with_representations(app, api):
    called_with = []

    def json_renderer(data, code, headers):
        called_with.append((data, code, headers))
        from flask import Response
        return Response(str(data), status=code, mimetype="application/json")

    class MyResource(Resource):
        representations = {"application/json": json_renderer}

        def get(self):
            return {"key": "value"}, 200, {}

    with app.test_request_context(
        "/", method="GET", headers={"Accept": "application/json"}
    ):
        resource = MyResource(api=api)
        resp = resource.dispatch_request()
        assert resp.status_code == 200


def test_dispatch_request_no_matching_representation(app, api):
    class MyResource(Resource):
        representations = {}

        def get(self):
            return {"key": "value"}

    with app.test_request_context("/", method="GET"):
        resource = MyResource(api=api)
        resp = resource.dispatch_request()
        assert resp == {"key": "value"}


def test_dispatch_request_asserts_unimplemented_method(app, api):
    class MyResource(Resource):
        def get(self):
            return {}

    with app.test_request_context("/", method="DELETE"):
        resource = MyResource(api=api)
        with pytest.raises(AssertionError, match="Unimplemented method"):
            resource.dispatch_request()


# Tests for Resource.validate_payload

def test_validate_payload_no_apidoc(api):
    resource = Resource(api=api)
    func = MagicMock(spec=[])  # no __apidoc__
    # Should not raise
    resource.validate_payload(func)


def test_validate_payload_apidoc_false(api):
    resource = Resource(api=api)
    func = MagicMock()
    func.__apidoc__ = False
    resource.validate_payload(func)


def test_validate_payload_no_validate_flag(api):
    resource = Resource(api=api)
    mock_api = MagicMock()
    mock_api._validate = False
    resource.api = mock_api

    func = MagicMock()
    func.__apidoc__ = {"validate": False, "expect": []}
    resource.validate_payload(func)


def test_validate_payload_validate_true_no_expect(api):
    resource = Resource(api=api)
    mock_api = MagicMock()
    mock_api._validate = True
    resource.api = mock_api

    func = MagicMock()
    func.__apidoc__ = {"validate": True, "expect": []}
    resource.validate_payload(func)


def test_validate_payload_uses_api_validate_when_doc_has_none(api):
    resource = Resource(api=api)
    mock_api = MagicMock()
    mock_api._validate = False
    resource.api = mock_api

    func = MagicMock()
    func.__apidoc__ = {"expect": []}
    # validate=None means fall back to api._validate which is False
    resource.validate_payload(func)


def test_validate_payload_with_model_base_expect(app, api):
    resource = Resource(api=api)
    mock_api = MagicMock()
    mock_api._validate = True
    resource.api = mock_api

    mock_model = MagicMock(spec=ModelBase)

    func = MagicMock()
    func.__apidoc__ = {"validate": True, "expect": [mock_model]}

    with app.test_request_context(
        "/", method="POST", json={"name": "test"}
    ):
        resource.validate_payload(func)

    mock_model.validate.assert_called_once()


def test_validate_payload_with_collection_expect(app, api):
    resource = Resource(api=api)
    mock_api = MagicMock()
    mock_api._validate = True
    resource.api = mock_api

    mock_model = MagicMock(spec=ModelBase)

    func = MagicMock()
    func.__apidoc__ = {"validate": True, "expect": [[mock_model]]}

    with app.test_request_context(
        "/", method="POST", json=[{"name": "test"}]
    ):
        resource.validate_payload(func)

    mock_model.validate.assert_called_once()


def test_validate_payload_collection_wraps_non_list_data(app, api):
    resource = Resource(api=api)
    mock_api = MagicMock()
    mock_api._validate = True
    resource.api = mock_api

    mock_model = MagicMock(spec=ModelBase)

    func = MagicMock()
    func.__apidoc__ = {"validate": True, "expect": [[mock_model]]}

    with app.test_request_context(
        "/", method="POST", json={"name": "test"}
    ):
        resource.validate_payload(func)

    mock_model.validate.assert_called_once()


def test_validate_payload_expect_list_with_non_model_base(api):
    resource = Resource(api=api)
    mock_api = MagicMock()
    mock_api._validate = True
    resource.api = mock_api

    # A list with one item that is NOT a ModelBase
    non_model = MagicMock()

    func = MagicMock()
    func.__apidoc__ = {"validate": True, "expect": [[non_model]]}

    # Should not raise since it's not a ModelBase
    resource.validate_payload(func)
