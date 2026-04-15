# -*- coding: utf-8 -*-
"""Tests for flask_restx.swagger module."""
import pytest
from collections import OrderedDict
from flask import Flask
from flask_restx import Api, Resource, Model, fields as restx_fields, Namespace
from flask_restx.swagger import (
    Swagger,
    ref,
    _v,
    extract_path,
    parse_rule,
    extract_path_params,
    _param_to_header,
    _clean_header,
    parse_docstring,
    is_hidden,
    build_request_body_parameters_schema,
    PY_TYPES,
)
from flask_restx.model import ModelBase


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def api(app):
    return Api(app)


@pytest.fixture
def swagger(api):
    return Swagger(api)


@pytest.fixture
def request_ctx(app):
    with app.test_request_context():
        yield app


# ---- ref ----

class RefTest:
    def test_ref_with_string(self):
        result = ref("MyModel")
        assert result == {"$ref": "#/definitions/MyModel"}

    def test_ref_with_model_base(self):
        m = Model("TestModel", {})
        result = ref(m)
        assert result == {"$ref": "#/definitions/TestModel"}

    def test_ref_with_special_chars_in_name(self):
        result = ref("My Model")
        assert result == {"$ref": "#/definitions/My%20Model"}


# ---- _v ----

class VTest:
    def test_v_with_non_callable(self):
        assert _v("hello") == "hello"
        assert _v(42) == 42
        assert _v(None) is None

    def test_v_with_callable(self):
        assert _v(lambda: "world") == "world"
        assert _v(lambda: 99) == 99


# ---- extract_path ----

class ExtractPathTest:
    def test_extract_path_simple(self):
        assert extract_path("/users/<int:id>") == "/users/{id}"

    def test_extract_path_multiple_params(self):
        assert extract_path("/users/<string:name>/posts/<int:post_id>") == "/users/{name}/posts/{post_id}"

    def test_extract_path_no_params(self):
        assert extract_path("/users/all") == "/users/all"

    def test_extract_path_without_converter(self):
        assert extract_path("/users/<id>") == "/users/{id}"


# ---- parse_rule ----

class ParseRuleTest:
    def test_parse_rule_static(self):
        result = list(parse_rule("/users/"))
        assert (None, None, "/users/") in result

    def test_parse_rule_dynamic(self):
        result = list(parse_rule("/users/<int:id>"))
        assert ("int", None, "id") in result

    def test_parse_rule_default_converter(self):
        result = list(parse_rule("/users/<id>"))
        assert ("default", None, "id") in result

    def test_parse_rule_duplicate_variable_raises(self):
        with pytest.raises(ValueError, match="used twice"):
            list(parse_rule("/<id>/<id>"))

    def test_parse_rule_malformed_url_raises(self):
        with pytest.raises(ValueError, match="malformed url rule"):
            list(parse_rule("/users/<broken>>"))

    def test_parse_rule_with_args(self):
        result = list(parse_rule("/<string(minlength=2):name>"))
        converters = [r[0] for r in result if r[0] is not None]
        assert "string" in converters

    def test_parse_rule_remaining_static_after_last_variable(self):
        result = list(parse_rule("/users/<id>/posts"))
        assert result[-1] == (None, None, "/posts")


# ---- extract_path_params ----

class ExtractPathParamsTest:
    def test_extract_path_params_integer(self, request_ctx):
        params = extract_path_params("/users/<int:id>")
        assert "id" in params
        assert params["id"]["type"] == "integer"
        assert params["id"]["in"] == "path"
        assert params["id"]["required"] is True

    def test_extract_path_params_string(self, request_ctx):
        params = extract_path_params("/users/<string:name>")
        assert params["name"]["type"] == "string"

    def test_extract_path_params_float(self, request_ctx):
        params = extract_path_params("/data/<float:value>")
        assert params["value"]["type"] == "number"

    def test_extract_path_params_default(self, request_ctx):
        params = extract_path_params("/users/<id>")
        assert params["id"]["type"] == "string"

    def test_extract_path_params_unsupported_converter(self, request_ctx):
        with pytest.raises(ValueError, match="Unsupported type converter"):
            extract_path_params("/users/<foobar:id>")

    def test_extract_path_params_multiple(self, request_ctx):
        params = extract_path_params("/users/<int:user_id>/posts/<string:title>")
        assert "user_id" in params
        assert "title" in params


# ---- _param_to_header ----

class ParamToHeaderTest:
    def test_removes_in_and_name(self):
        param = {"in": "header", "name": "X-Custom", "type": "string"}
        result = _param_to_header(param)
        assert "in" not in result
        assert "name" not in result
        assert result["type"] == "string"

    def test_works_with_minimal_param(self):
        param = {"description": "some header"}
        result = _param_to_header(param)
        assert result["type"] == "string"


# ---- _clean_header ----

class CleanHeaderTest:
    def test_string_becomes_description(self):
        result = _clean_header("My description")
        assert result["description"] == "My description"
        assert result["type"] == "string"

    def test_dict_with_type_string(self):
        result = _clean_header({"type": "string"})
        assert result["type"] == "string"

    def test_dict_with_python_type_int(self):
        result = _clean_header({"type": int})
        assert result["type"] == "integer"

    def test_dict_with_list_type(self):
        result = _clean_header({"type": [str]})
        assert result["type"] == "array"
        assert result["items"] == {"type": "string"}

    def test_dict_with_schema_object(self):
        class FakeField:
            __schema__ = {"type": "object"}
        result = _clean_header({"type": FakeField()})
        assert result["type"] == "object"

    def test_dict_with_unknown_type(self):
        result = _clean_header({"type": "custom_type"})
        assert result["type"] == "custom_type"

    def test_none_values_removed(self):
        result = _clean_header({"description": None, "type": "string"})
        assert "description" not in result


# ---- parse_docstring ----

class ParseDocstringTest:
    def test_parse_docstring_with_docstring(self):
        def my_func():
            """A simple summary.

            Some details here.
            """
        result = parse_docstring(my_func)
        assert result["summary"] == "A simple summary"
        assert result["details"] == "Some details here."
        assert result["raises"] == {}

    def test_parse_docstring_no_docstring(self):
        def my_func():
            pass
        result = parse_docstring(my_func)
        assert result["summary"] is None
        assert result["details"] is None
        assert result["raises"] == {}

    def test_parse_docstring_with_raises(self):
        def my_func():
            """:raises ValueError: When the value is wrong."""
        result = parse_docstring(my_func)
        assert "ValueError" in result["raises"]
        assert result["raises"]["ValueError"] == "When the value is wrong."

    def test_parse_docstring_returns_none(self):
        def my_func():
            """Summary only."""
        result = parse_docstring(my_func)
        assert result["returns"] is None

    def test_parse_docstring_params_empty_list(self):
        def my_func():
            """Summary."""
        result = parse_docstring(my_func)
        assert result["params"] == []


# ---- is_hidden ----

class IsHiddenTest:
    def test_route_doc_false_returns_true(self):
        class FakeResource:
            pass
        assert is_hidden(FakeResource, route_doc=False) is True

    def test_apidoc_false_returns_true(self):
        class FakeResource:
            __apidoc__ = False
        assert is_hidden(FakeResource) is True

    def test_no_apidoc_returns_false(self):
        class FakeResource:
            pass
        assert is_hidden(FakeResource) is False

    def test_apidoc_dict_returns_false(self):
        class FakeResource:
            __apidoc__ = {"description": "some resource"}
        assert is_hidden(FakeResource) is False

    def test_route_doc_dict_not_hidden(self):
        class FakeResource:
            pass
        assert is_hidden(FakeResource, route_doc={"description": "ok"}) is False


# ---- build_request_body_parameters_schema ----

class BuildRequestBodyParametersSchemaTest:
    def test_basic(self):
        body_params = [
            {"name": "username", "type": "string"},
            {"name": "age", "type": "integer"},
        ]
        result = build_request_body_parameters_schema(body_params)
        assert result["name"] == "payload"
        assert result["required"] is True
        assert result["in"] == "body"
        assert result["schema"]["type"] == "object"
        assert "username" in result["schema"]["properties"]
        assert result["schema"]["properties"]["username"] == {"type": "string"}
        assert result["schema"]["properties"]["age"] == {"type": "integer"}

    def test_empty_params(self):
        result = build_request_body_parameters_schema([])
        assert result["schema"]["properties"] == {}

    def test_default_type_string(self):
        body_params = [{"name": "field"}]
        result = build_request_body_parameters_schema(body_params)
        assert result["schema"]["properties"]["field"] == {"type": "string"}


# ---- Swagger class ----

class SwaggerInitTest:
    def test_init(self, api):
        s = Swagger(api)
        assert s.api is api
        assert s._registered_models == {}


class SwaggerGetHostTest:
    def test_get_host_no_server_name(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            assert s.get_host() is None

    def test_get_host_with_server_name(self, app, api):
        app.config["SERVER_NAME"] = "example.com"
        with app.test_request_context():
            s = Swagger(api)
            assert s.get_host() == "example.com"

    def test_get_host_with_subdomain(self, app):
        from flask import Blueprint
        bp = Blueprint("test_bp", __name__, subdomain="sub")
        api = Api(bp)
        app.config["SERVER_NAME"] = "example.com"
        app.register_blueprint(bp)
        with app.test_request_context():
            s = Swagger(api)
            assert s.get_host() == "sub.example.com"


class SwaggerExtractTagsTest:
    def test_extract_tags_string(self, app, api):
        with app.test_request_context():
            api.tags = ["tag1", "tag2"]
            s = Swagger(api)
            tags = s.extract_tags(api)
            names = [t["name"] for t in tags]
            assert "tag1" in names
            assert "tag2" in names

    def test_extract_tags_list_tuple(self, app, api):
        with app.test_request_context():
            api.tags = [("mytag", "my description")]
            s = Swagger(api)
            tags = s.extract_tags(api)
            assert tags[0] == {"name": "mytag", "description": "my description"}

    def test_extract_tags_dict(self, app, api):
        with app.test_request_context():
            api.tags = [{"name": "mytag", "description": "desc"}]
            s = Swagger(api)
            tags = s.extract_tags(api)
            assert tags[0]["name"] == "mytag"

    def test_extract_tags_invalid_raises(self, app, api):
        with app.test_request_context():
            api.tags = [12345]
            s = Swagger(api)
            with pytest.raises(ValueError, match="Unsupported tag format"):
                s.extract_tags(api)

    def test_extract_tags_from_namespace(self, app):
        api = Api(app)
        ns = api.namespace("testns", description="A test namespace")

        @ns.route("/something")
        class SomeResource(Resource):
            def get(self):
                pass

        with app.test_request_context():
            s = Swagger(api)
            tags = s.extract_tags(api)
            ns_names = [t["name"] for t in tags]
            assert "testns" in ns_names


class SwaggerVendorFieldsTest:
    def test_vendor_fields_with_x_prefix(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {"get": {"vendor": {"x-custom": "value"}}}
            result = s.vendor_fields(doc, "get")
            assert result["x-custom"] == "value"

    def test_vendor_fields_without_x_prefix(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {"get": {"vendor": {"custom": "value"}}}
            result = s.vendor_fields(doc, "get")
            assert result["x-custom"] == "value"

    def test_vendor_fields_empty(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {"get": {"vendor": {}}}
            result = s.vendor_fields(doc, "get")
            assert result == {}

    def test_vendor_fields_no_vendor_key(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {"get": {}}
            result = s.vendor_fields(doc, "get")
            assert result == {}


class SwaggerDescriptionForTest:
    def test_description_for_from_doc(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "description": "top-level description",
                "get": {"description": "method desc", "docstring": {"details": None}},
            }
            result = s.description_for(doc, "get")
            assert "top-level description" in result
            assert "method desc" in result

    def test_description_for_from_docstring(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "get": {"docstring": {"details": "docstring details"}},
            }
            result = s.description_for(doc, "get")
            assert "docstring details" in result

    def test_description_for_empty(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {"get": {"docstring": {"details": None}}}
            result = s.description_for(doc, "get")
            assert result == ""


class SwaggerOperationIdForTest:
    def test_operation_id_with_custom_id(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {"name": "MyResource", "get": {"id": "custom_id"}}
            result = s.operation_id_for(doc, "get")
            assert result == "custom_id"

    def test_operation_id_default(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {"name": "MyResource", "get": {}}
            result = s.operation_id_for(doc, "get")
            assert result == api.default_id("MyResource", "get")


class SwaggerSecurityRequirementTest:
    def test_security_requirement_string(self, api):
        s = Swagger(api)
        result = s.security_requirement("apikey")
        assert result == {"apikey": []}

    def test_security_requirement_dict(self, api):
        s = Swagger(api)
        result = s.security_requirement({"oauth2": ["read", "write"]})
        assert result == {"oauth2": ["read", "write"]}

    def test_security_requirement_dict_scalar_value(self, api):
        s = Swagger(api)
        result = s.security_requirement({"oauth2": "read"})
        assert result == {"oauth2": ["read"]}

    def test_security_requirement_other_returns_none(self, api):
        s = Swagger(api)
        result = s.security_requirement(42)
        assert result is None


class SwaggerSecurityRequirementsTest:
    def test_security_requirements_list(self, api):
        s = Swagger(api)
        result = s.security_requirements(["apikey", "oauth2"])
        assert {"apikey": []} in result
        assert {"oauth2": []} in result

    def test_security_requirements_single(self, api):
        s = Swagger(api)
        result = s.security_requirements("apikey")
        assert result == [{"apikey": []}]

    def test_security_requirements_falsy(self, api):
        s = Swagger(api)
        assert s.security_requirements(None) == []
        assert s.security_requirements("") == []

    def test_security_requirements_returns_none_for_invalid(self, api):
        s = Swagger(api)
        result = s.security_requirements(42)
        assert result is None


class SwaggerSecurityForTest:
    def test_security_for_no_security(self, api):
        s = Swagger(api)
        doc = {"get": {}}
        result = s.security_for(doc, "get")
        assert result is None

    def test_security_for_doc_level(self, api):
        s = Swagger(api)
        doc = {"security": "apikey", "get": {}}
        result = s.security_for(doc, "get")
        assert result == [{"apikey": []}]

    def test_security_for_method_level_overrides(self, api):
        s = Swagger(api)
        doc = {"security": "apikey", "get": {"security": "oauth2"}}
        result = s.security_for(doc, "get")
        assert result == [{"oauth2": []}]


class SwaggerSerializeDefinitionsTest:
    def test_serialize_definitions_empty(self, api):
        s = Swagger(api)
        result = s.serialize_definitions()
        assert result == {}

    def test_serialize_definitions_with_model(self, app, api):
        model = api.model("MyModel", {"field": restx_fields.String()})
        with app.test_request_context():
            s = Swagger(api)
            s.register_model(model)
            result = s.serialize_definitions()
            assert "MyModel" in result


class SwaggerSerializeSchemaTest:
    def test_serialize_schema_list(self, app, api):
        model = api.model("AModel", {"name": restx_fields.String()})
        with app.test_request_context():
            s = Swagger(api)
            result = s.serialize_schema([model])
            assert result["type"] == "array"
            assert "$ref" in result["items"]

    def test_serialize_schema_model_base(self, app, api):
        model = api.model("BModel", {"name": restx_fields.String()})
        with app.test_request_context():
            s = Swagger(api)
            result = s.serialize_schema(model)
            assert "$ref" in result

    def test_serialize_schema_string_model(self, app, api):
        api.model("CModel", {"name": restx_fields.String()})
        with app.test_request_context():
            s = Swagger(api)
            result = s.serialize_schema("CModel")
            assert "$ref" in result

    def test_serialize_schema_field_class(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            result = s.serialize_schema(restx_fields.String)
            assert "type" in result

    def test_serialize_schema_field_instance(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            result = s.serialize_schema(restx_fields.String())
            assert "type" in result

    def test_serialize_schema_py_type(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            result = s.serialize_schema(int)
            assert result == {"type": "integer"}

    def test_serialize_schema_invalid_raises(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            with pytest.raises(ValueError, match="not registered"):
                s.serialize_schema(object())


class SwaggerRegisterModelTest:
    def test_register_model_success(self, app, api):
        model = api.model("DModel", {"name": restx_fields.String()})
        with app.test_request_context():
            s = Swagger(api)
            result = s.register_model(model)
            assert "$ref" in result
            assert "DModel" in s._registered_models

    def test_register_model_not_registered_raises(self, app, api):
        model = Model("Unregistered", {})
        with app.test_request_context():
            s = Swagger(api)
            with pytest.raises(ValueError, match="not registered"):
                s.register_model(model)

    def test_register_model_idempotent(self, app, api):
        model = api.model("EModel", {"name": restx_fields.String()})
        with app.test_request_context():
            s = Swagger(api)
            s.register_model(model)
            result = s.register_model(model)
            assert "$ref" in result


class SwaggerRegisterFieldTest:
    def test_register_field_nested(self, app, api):
        inner_model = api.model("InnerModel", {"val": restx_fields.Integer()})
        with app.test_request_context():
            s = Swagger(api)
            nested_field = restx_fields.Nested(inner_model)
            s.register_field(nested_field)
            assert "InnerModel" in s._registered_models

    def test_register_field_list(self, app, api):
        inner_model = api.model("ListInnerModel", {"val": restx_fields.Integer()})
        with app.test_request_context():
            s = Swagger(api)
            list_field = restx_fields.List(restx_fields.Nested(inner_model))
            s.register_field(list_field)
            assert "ListInnerModel" in s._registered_models

    def test_register_field_non_special_is_no_op(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            s.register_field(restx_fields.String())
            assert s._registered_models == {}


class SwaggerProcessHeadersTest:
    def test_process_headers_with_headers_in_doc(self, api):
        s = Swagger(api)
        response = {}
        doc = {"headers": {"X-Custom": "my header"}, "get": {}}
        result = s.process_headers(response, doc, "get")
        assert "headers" in result
        assert "X-Custom" in result["headers"]

    def test_process_headers_no_headers(self, api):
        s = Swagger(api)
        response = {}
        doc = {"get": {}}
        result = s.process_headers(response, doc, "get")
        assert "headers" not in result

    def test_process_headers_with_explicit_headers(self, api):
        s = Swagger(api)
        response = {}
        doc = {"get": {}}
        result = s.process_headers(response, doc, "get", headers={"X-Rate": "string"})
        assert "headers" in result
        assert "X-Rate" in result["headers"]


class SwaggerParametersForTest:
    def test_parameters_for_basic(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "params": OrderedDict([
                    ("name", {"in": "query", "type": "string"}),
                ])
            }
            params = s.parameters_for(doc)
            assert len(params) == 1
            assert params[0]["name"] == "name"

    def test_parameters_for_default_type_string(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {"params": OrderedDict([("q", {"in": "query"})])}
            params = s.parameters_for(doc)
            assert params[0]["type"] == "string"

    def test_parameters_for_default_in_query(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {"params": OrderedDict([("q", {"type": "string"})])}
            params = s.parameters_for(doc)
            assert params[0]["in"] == "query"

    def test_parameters_for_list_type(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {"params": OrderedDict([("ids", {"type": [int], "in": "query"})])}
            params = s.parameters_for(doc)
            assert params[0]["type"] == "array"
            assert params[0]["items"] == {"type": "integer"}

    def test_parameters_for_py_type(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {"params": OrderedDict([("count", {"type": int, "in": "query"})])}
            params = s.parameters_for(doc)
            assert params[0]["type"] == "integer"

    def test_parameters_for_mask(self, app, api):
        app.config["RESTX_MASK_SWAGGER"] = True
        app.config["RESTX_MASK_HEADER"] = "X-Fields"
        with app.test_request_context():
            s = Swagger(api)
            doc = {"params": OrderedDict(), "__mask__": True}
            params = s.parameters_for(doc)
            assert any(p["name"] == "X-Fields" for p in params)


class SwaggerAsDictTest:
    def test_as_dict_basic(self, app):
        api = Api(app, version="1.0", title="Test API")

        @api.route("/hello")
        class Hello(Resource):
            def get(self):
                """Say hello."""
                pass

        with app.test_request_context():
            s = Swagger(api)
            d = s.as_dict()
            assert d["swagger"] == "2.0"
            assert d["info"]["title"] == "Test API"
            assert d["info"]["version"] == "1.0"

    def test_as_dict_strips_trailing_slash_from_basepath(self, app):
        # Create a Flask app with a prefix that ends in a slash
        from flask import Blueprint
        bp = Blueprint("api_bp2", __name__, url_prefix="/api/")
        api = Api(bp)
        app.register_blueprint(bp)
        with app.test_request_context():
            s = Swagger(api)
            d = s.as_dict()
            # as_dict() should strip the trailing slash from basepath
            assert not d["basePath"].endswith("/")

    def test_as_dict_with_description(self, app):
        api = Api(app, description="My API description")
        with app.test_request_context():
            s = Swagger(api)
            d = s.as_dict()
            assert d["info"]["description"] == "My API description"

    def test_as_dict_with_terms_url(self, app):
        api = Api(app, terms_url="http://terms.example.com")
        with app.test_request_context():
            s = Swagger(api)
            d = s.as_dict()
            assert d["info"]["termsOfService"] == "http://terms.example.com"

    def test_as_dict_with_contact(self, app):
        api = Api(app, contact="admin", contact_email="admin@example.com")
        with app.test_request_context():
            s = Swagger(api)
            d = s.as_dict()
            assert d["info"]["contact"]["name"] == "admin"

    def test_as_dict_with_license(self, app):
        api = Api(app, license="MIT", license_url="http://mit.example.com")
        with app.test_request_context():
            s = Swagger(api)
            d = s.as_dict()
            assert d["info"]["license"]["name"] == "MIT"
            assert d["info"]["license"]["url"] == "http://mit.example.com"


class SwaggerRegisterErrorsTest:
    def test_register_errors_empty(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            result = s.register_errors()
            assert isinstance(result, dict)

    def test_register_errors_with_handler(self, app, api):
        class MyError(Exception):
            pass

        @api.errorhandler(MyError)
        def handle_my_error(e):
            """My error description."""
            pass

        with app.test_request_context():
            s = Swagger(api)
            result = s.register_errors()
            assert "MyError" in result


class SwaggerResponsesForTest:
    def test_responses_for_default(self, app, api):
        @api.route("/test")
        class TestResource(Resource):
            def get(self):
                """Get something."""
                pass

        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "get": {
                    "docstring": {"summary": "Get something", "raises": {}},
                },
            }
            responses = s.responses_for(doc, "get")
            assert "200" in responses

    def test_responses_for_string_response(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "responses": {"200": "Success"},
                "get": {
                    "docstring": {"summary": "ok", "raises": {}},
                },
            }
            responses = s.responses_for(doc, "get")
            assert responses["200"]["description"] == "Success"

    def test_responses_for_tuple_2(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "responses": {"404": ("Not found", None)},
                "get": {
                    "docstring": {"summary": "ok", "raises": {}},
                },
            }
            responses = s.responses_for(doc, "get")
            assert responses["404"]["description"] == "Not found"

    def test_responses_for_invalid_response_raises(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "responses": {"200": (1, 2, 3, 4)},
                "get": {
                    "docstring": {"summary": "ok", "raises": {}},
                },
            }
            with pytest.raises(ValueError, match="Unsupported response specification"):
                s.responses_for(doc, "get")


    def test_responses_for_tuple_3(self, app, api):
        model = api.model("Tuple3Model", {"name": restx_fields.String()})
        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "responses": {"201": ("Created", model, {})},
                "get": {"docstring": {"summary": "ok", "raises": {}}},
            }
            responses = s.responses_for(doc, "get")
            assert responses["201"]["description"] == "Created"
            assert "schema" in responses["201"]

    def test_responses_for_code_already_in_responses(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "responses": {"200": "Top level"},
                "get": {
                    "responses": {"200": "Method level"},
                    "docstring": {"summary": "ok", "raises": {}},
                },
            }
            responses = s.responses_for(doc, "get")
            assert responses["200"]["description"] == "Method level"

    def test_responses_for_with_model_in_response(self, app, api):
        model = api.model("ResponseModel", {"name": restx_fields.String()})
        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "responses": {"200": ("OK", model, {})},
                "get": {"docstring": {"summary": "ok", "raises": {}}},
            }
            responses = s.responses_for(doc, "get")
            assert "schema" in responses["200"]

    def test_responses_for_with_model_and_envelope(self, app, api):
        model = api.model("EnvelopeModel", {"name": restx_fields.String()})
        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "responses": {"200": ("OK", model, {"envelope": "data"})},
                "get": {"docstring": {"summary": "ok", "raises": {}}},
            }
            responses = s.responses_for(doc, "get")
            assert "schema" in responses["200"]
            assert "properties" in responses["200"]["schema"]
            assert "data" in responses["200"]["schema"]["properties"]

    def test_responses_for_model_in_doc(self, app, api):
        model = api.model("DocModel", {"name": restx_fields.String()})
        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "model": model,
                "get": {"docstring": {"summary": "ok", "raises": {}}},
            }
            responses = s.responses_for(doc, "get")
            assert "200" in responses
            assert "schema" in responses["200"]

    def test_responses_for_model_with_default_code(self, app, api):
        from flask_restx._http import HTTPStatus
        model = api.model("DefaultCodeModel", {"name": restx_fields.String()})
        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "model": model,
                "default_code": 201,
                "get": {"docstring": {"summary": "ok", "raises": {}}},
            }
            responses = s.responses_for(doc, "get")
            assert "201" in responses
            assert "schema" in responses["201"]

    def test_responses_for_model_in_doc_with_existing_response(self, app, api):
        model = api.model("ExistingRespModel", {"name": restx_fields.String()})
        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "responses": {"200": "Already here"},
                "model": model,
                "get": {"docstring": {"summary": "ok", "raises": {}}},
            }
            responses = s.responses_for(doc, "get")
            assert "schema" in responses["200"]

    def test_responses_for_docstring_raises_with_matching_error_handler(self, app, api):
        class MyCustomError(Exception):
            pass

        def my_handler(e):
            pass

        my_handler.__apidoc__ = {"responses": {400: "Bad request"}}
        api.error_handlers[MyCustomError] = my_handler

        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "get": {
                    "docstring": {
                        "summary": "ok",
                        "raises": {"MyCustomError": "Some error"},
                    },
                },
            }
            responses = s.responses_for(doc, "get")
            assert "400" in responses
            assert "$ref" in responses["400"]

    def test_responses_for_docstring_raises_no_matching_handler(self, app, api):
        class UnhandledError(Exception):
            pass

        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "get": {
                    "docstring": {
                        "summary": "ok",
                        "raises": {"UnhandledError": "Some error"},
                    },
                },
            }
            responses = s.responses_for(doc, "get")
            assert "200" in responses

    def test_responses_for_docstring_raises_handler_without_apidoc(self, app, api):
        class AnotherError(Exception):
            pass

        api.error_handlers[AnotherError] = lambda e: None

        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "get": {
                    "docstring": {
                        "summary": "ok",
                        "raises": {"AnotherError": "Some error"},
                    },
                },
            }
            responses = s.responses_for(doc, "get")
            assert "200" in responses


class SwaggerSerializeResourceTest:
    def test_serialize_resource_hidden(self, app, api):
        class HiddenResource(Resource):
            __apidoc__ = False
            methods = ["GET"]

            def get(self):
                pass

        with app.test_request_context():
            s = Swagger(api)
            result = s.serialize_resource(api.default_namespace, HiddenResource, "/hidden", route_doc=False)
            assert result is None

    def test_serialize_resource_basic(self, app):
        api = Api(app)

        @api.route("/foo")
        class FooResource(Resource):
            def get(self):
                """Get foo."""
                pass

        with app.test_request_context():
            s = Swagger(api)
            ns = api.default_namespace
            result = s.serialize_resource(ns, FooResource, "/foo")
            assert result is not None
            assert "get" in result


class SwaggerSerializeOperationTest:
    def test_serialize_operation_basic(self, app, api):
        @api.route("/ops")
        class OpsResource(Resource):
            def get(self):
                """Get ops."""
                pass

        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "name": "OpsResource",
                "get": {
                    "docstring": {"summary": "Get ops", "details": None, "raises": {}},
                    "params": OrderedDict(),
                    "vendor": {},
                },
                "params": OrderedDict(),
            }
            result = s.serialize_operation(doc, "get")
            assert "responses" in result
            assert result["summary"] == "Get ops"

    def test_serialize_operation_deprecated(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "name": "OpsResource",
                "deprecated": True,
                "get": {
                    "docstring": {"summary": "Get", "details": None, "raises": {}},
                    "params": OrderedDict(),
                    "vendor": {},
                },
                "params": OrderedDict(),
            }
            result = s.serialize_operation(doc, "get")
            assert result.get("deprecated") is True

    def test_serialize_operation_produces(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            doc = {
                "name": "OpsResource",
                "get": {
                    "docstring": {"summary": "Get", "details": None, "raises": {}},
                    "params": OrderedDict(),
                    "vendor": {},
                    "produces": ["application/xml"],
                },
                "params": OrderedDict(),
            }
            result = s.serialize_operation(doc, "get")
            assert result["produces"] == ["application/xml"]


class SwaggerExpectedParamsTest:
    def test_expected_params_no_expect(self, app, api):
        with app.test_request_context():
            s = Swagger(api)
            result = s.expected_params({})
            assert result == OrderedDict()

    def test_expected_params_with_model(self, app, api):
        model = api.model("ExpModel", {"name": restx_fields.String()})
        with app.test_request_context():
            s = Swagger(api)
            result = s.expected_params({"expect": [model]})
            assert "payload" in result

    def test_expected_params_with_list_tuple_2(self, app, api):
        model = api.model("ListTupleModel", {"name": restx_fields.String()})
        with app.test_request_context():
            s = Swagger(api)
            result = s.expected_params({"expect": [(model, "My payload")]})
            assert "payload" in result
            assert result["payload"]["description"] == "My payload"

    def test_expected_params_with_request_parser(self, app, api):
        from flask_restx import reqparse
        parser = reqparse.RequestParser()
        parser.add_argument("name", type=str, help="Name")
        with app.test_request_context():
            s = Swagger(api)
            result = s.expected_params({"expect": [parser]})
            assert "name" in result
