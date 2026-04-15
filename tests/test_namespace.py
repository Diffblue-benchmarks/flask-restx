"""
Tests for flask_restx.namespace module.
"""
import warnings
import pytest
from flask import Flask
from werkzeug.exceptions import HTTPException

from flask_restx import Api, Resource
from flask_restx import fields as restx_fields
from flask_restx.namespace import (
    Namespace,
    unshortcut_params_description,
    handle_deprecations,
)
from flask_restx.reqparse import RequestParser


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def ns():
    return Namespace("test", description="A test namespace")


# ---------------------------------------------------------------------------
# Namespace.__init__
# ---------------------------------------------------------------------------

class NamespaceInitTest:
    def test_defaults(self):
        n = Namespace("myns")
        assert n.name == "myns"
        assert n.description is None
        assert n._path is None
        assert n._schema is None
        assert n._validate is None
        assert n.models == {}
        assert n.urls == {}
        assert n.decorators == []
        assert n.resources == []
        assert n.error_handlers == {}
        assert n.default_error_handler is None
        assert n.authorizations is None
        assert n.ordered is False
        assert n.apis == []

    def test_with_description(self):
        n = Namespace("myns", description="desc")
        assert n.description == "desc"

    def test_with_path(self):
        n = Namespace("myns", path="/custom")
        assert n._path == "/custom"

    def test_with_validate(self):
        n = Namespace("myns", validate=True)
        assert n._validate is True

    def test_with_authorizations(self):
        n = Namespace("myns", authorizations={"apikey": {}})
        assert n.authorizations == {"apikey": {}}

    def test_with_ordered(self):
        n = Namespace("myns", ordered=True)
        assert n.ordered is True

    def test_with_decorators(self):
        decorator = lambda f: f
        n = Namespace("myns", decorators=[decorator])
        assert n.decorators == [decorator]

    def test_with_api_kwarg(self, app):
        api = Api(app)
        n = Namespace("myns", api=api)
        assert api in n.apis

    def test_logger_name(self):
        n = Namespace("myns")
        import logging
        assert n.logger.name == "flask_restx.namespace.myns"


# ---------------------------------------------------------------------------
# Namespace.path property
# ---------------------------------------------------------------------------

class NamespacePathTest:
    def test_path_with_explicit_path(self):
        n = Namespace("myns", path="/custom/path")
        assert n.path == "/custom/path"

    def test_path_defaults_to_name(self):
        n = Namespace("myns")
        assert n.path == "/myns"

    def test_path_strips_trailing_slash(self):
        n = Namespace("myns", path="/custom/")
        assert n.path == "/custom"


# ---------------------------------------------------------------------------
# Namespace.add_resource
# ---------------------------------------------------------------------------

class NamespaceAddResourceTest:
    def test_add_resource_stores_route(self, ns):
        class Dummy(Resource):
            pass

        ns.add_resource(Dummy, "/dummy")
        assert len(ns.resources) == 1
        route = ns.resources[0]
        assert route.resource is Dummy
        assert "/dummy" in route.urls

    def test_add_resource_multiple_urls(self, ns):
        class Dummy(Resource):
            pass

        ns.add_resource(Dummy, "/a", "/b")
        assert len(ns.resources) == 1
        route = ns.resources[0]
        assert "/a" in route.urls
        assert "/b" in route.urls

    def test_add_resource_with_route_doc(self, ns):
        class Dummy(Resource):
            pass

        ns.add_resource(Dummy, "/dummy", route_doc={"description": "test"})
        route = ns.resources[0]
        assert route.route_doc == {"description": "test"}

    def test_add_resource_registers_with_api(self, app):
        api = Api(app)
        test_ns = api.namespace("testns", path="/testns")

        class Dummy(Resource):
            def get(self):
                return {}

        test_ns.add_resource(Dummy, "/dummy")
        with app.test_client() as client:
            resp = client.get("/testns/dummy")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Namespace.route
# ---------------------------------------------------------------------------

class NamespaceRouteTest:
    def test_route_decorator_registers_resource(self, ns):
        @ns.route("/hello")
        class Hello(Resource):
            pass

        assert len(ns.resources) == 1
        assert ns.resources[0].resource is Hello

    def test_route_returns_class(self, ns):
        @ns.route("/hello")
        class Hello(Resource):
            pass

        assert Hello.__name__ == "Hello"

    def test_route_with_doc(self, ns):
        @ns.route("/hello", doc={"description": "A greeting"})
        class Hello(Resource):
            pass

        assert len(ns.resources) == 1
        route_doc = ns.resources[0].route_doc
        assert route_doc is not False

    def test_route_with_doc_false(self, ns):
        @ns.route("/hello", doc=False)
        class Hello(Resource):
            pass

        assert ns.resources[0].route_doc is False


# ---------------------------------------------------------------------------
# Namespace._build_doc
# ---------------------------------------------------------------------------

class NamespaceBuildDocTest:
    def test_build_doc_false(self, ns):
        result = ns._build_doc(object, False)
        assert result is False

    def test_build_doc_merges_with_class_apidoc(self, ns):
        class Documented:
            __apidoc__ = {"description": "existing"}

        result = ns._build_doc(Documented, {"summary": "new"})
        assert "description" in result
        assert "summary" in result

    def test_build_doc_unshortcuts_params(self, ns):
        doc = {"params": {"name": "a name"}}
        result = ns._build_doc(object, doc)
        assert result["params"]["name"] == {"description": "a name"}

    def test_build_doc_handles_http_methods(self, ns):
        doc = {"get": {"params": {"id": "the id"}}}
        result = ns._build_doc(object, doc)
        assert result["get"]["params"]["id"] == {"description": "the id"}

    def test_build_doc_expect_wrapped_in_list(self, ns):
        doc = {"get": {"expect": "some_model"}}
        result = ns._build_doc(object, doc)
        assert isinstance(result["get"]["expect"], list)

    def test_build_doc_expect_already_list(self, ns):
        doc = {"get": {"expect": ["some_model"]}}
        result = ns._build_doc(object, doc)
        assert result["get"]["expect"] == ["some_model"]

    def test_build_doc_http_method_false(self, ns):
        doc = {"get": False}
        result = ns._build_doc(object, doc)
        assert result["get"] is False


# ---------------------------------------------------------------------------
# Namespace.doc
# ---------------------------------------------------------------------------

class NamespaceDocTest:
    def test_doc_decorator_sets_apidoc(self, ns):
        @ns.doc(description="test")
        def my_func():
            pass

        assert hasattr(my_func, "__apidoc__")
        assert my_func.__apidoc__["description"] == "test"

    def test_doc_with_string_shortcut(self, ns):
        @ns.doc("my-operation-id")
        def my_func():
            pass

        assert my_func.__apidoc__["id"] == "my-operation-id"

    def test_doc_with_false_shortcut(self, ns):
        @ns.doc(False)
        def my_func():
            pass

        assert my_func.__apidoc__ is False

    def test_doc_returns_decorated(self, ns):
        def my_func():
            pass

        result = ns.doc(description="test")(my_func)
        assert result is my_func


# ---------------------------------------------------------------------------
# Namespace.hide
# ---------------------------------------------------------------------------

class NamespaceHideTest:
    def test_hide_sets_apidoc_false(self, ns):
        @ns.hide
        def my_func():
            pass

        assert my_func.__apidoc__ is False


# ---------------------------------------------------------------------------
# Namespace.abort
# ---------------------------------------------------------------------------

class NamespaceAbortTest:
    def test_abort_raises_http_exception(self, app, ns):
        with app.test_request_context("/"):
            with pytest.raises(HTTPException) as exc_info:
                ns.abort(404)
            assert exc_info.value.code == 404

    def test_abort_with_message(self, app, ns):
        with app.test_request_context("/"):
            with pytest.raises(HTTPException):
                ns.abort(400, "Bad Request")


# ---------------------------------------------------------------------------
# Namespace.add_model
# ---------------------------------------------------------------------------

class NamespaceAddModelTest:
    def test_add_model_stores_in_models(self, ns):
        from flask_restx.model import Model
        m = Model("MyModel", {})
        result = ns.add_model("MyModel", m)
        assert ns.models["MyModel"] is m
        assert result is m

    def test_add_model_propagates_to_apis(self, app):
        api = Api(app)
        test_ns = api.namespace("testns")
        from flask_restx.model import Model
        m = Model("MyModel", {})
        test_ns.add_model("MyModel", m)
        assert "MyModel" in api.models


# ---------------------------------------------------------------------------
# Namespace.model
# ---------------------------------------------------------------------------

class NamespaceModelTest:
    def test_model_creates_and_registers(self, ns):
        m = ns.model("User", {"name": restx_fields.String()})
        assert "User" in ns.models
        assert ns.models["User"] is m

    def test_model_ordered(self):
        n = Namespace("myns", ordered=True)
        from flask_restx.model import OrderedModel
        m = n.model("User", {"name": restx_fields.String()})
        assert isinstance(m, OrderedModel)

    def test_model_unordered(self):
        n = Namespace("myns", ordered=False)
        from flask_restx.model import Model
        m = n.model("User", {"name": restx_fields.String()})
        assert isinstance(m, Model)

    def test_model_with_kwargs(self, ns):
        m = ns.model("User", {"name": restx_fields.String()}, description="A user")
        assert m.__apidoc__["description"] == "A user"


# ---------------------------------------------------------------------------
# Namespace.schema_model
# ---------------------------------------------------------------------------

class NamespaceSchemaModelTest:
    def test_schema_model_creates_and_registers(self, ns):
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        m = ns.schema_model("UserSchema", schema)
        assert "UserSchema" in ns.models
        assert ns.models["UserSchema"] is m

    def test_schema_model_returns_schema_model_instance(self, ns):
        from flask_restx.model import SchemaModel
        m = ns.schema_model("MySchema", {})
        assert isinstance(m, SchemaModel)


# ---------------------------------------------------------------------------
# Namespace.extend
# ---------------------------------------------------------------------------

class NamespaceExtendTest:
    def test_extend_with_parent_model_raises(self, ns):
        # Model.extend is an instance method; Namespace.extend calls it incorrectly
        # as Model.extend(name_str, parent, fields), causing AttributeError on name_str.clone
        parent = ns.model("Parent", {"name": restx_fields.String()})
        with pytest.raises(AttributeError):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                ns.extend("Child", parent, {"age": restx_fields.Integer()})

    def test_extend_with_list_of_parents_raises(self, ns):
        parent1 = ns.model("Parent1", {"name": restx_fields.String()})
        parent2 = ns.model("Parent2", {"email": restx_fields.String()})
        with pytest.raises((AttributeError, TypeError)):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                ns.extend("Child2", [parent1, parent2], {"age": restx_fields.Integer()})


# ---------------------------------------------------------------------------
# Namespace.clone
# ---------------------------------------------------------------------------

class NamespaceCloneTest:
    def test_clone_duplicates_fields(self, ns):
        original = ns.model("Original", {"name": restx_fields.String()})
        cloned = ns.clone("Cloned", original)
        assert "Cloned" in ns.models
        assert "name" in cloned

    def test_clone_with_extra_fields(self, ns):
        from flask_restx.model import Model
        original = ns.model("Base", {"name": restx_fields.String()})
        extra = Model("Extra", {"age": restx_fields.Integer()})
        cloned = ns.clone("ClonedExtra", original, extra)
        assert "ClonedExtra" in ns.models


# ---------------------------------------------------------------------------
# Namespace.inherit
# ---------------------------------------------------------------------------

class NamespaceInheritTest:
    def test_inherit_creates_model(self, ns):
        parent = ns.model("ParentInherit", {"name": restx_fields.String()})
        child = ns.inherit("ChildInherit", parent, {"age": restx_fields.Integer()})
        assert "ChildInherit" in ns.models

    def test_inherit_returns_model(self, ns):
        parent = ns.model("ParentInherit2", {"name": restx_fields.String()})
        child = ns.inherit("ChildInherit2", parent, {"age": restx_fields.Integer()})
        assert child is ns.models["ChildInherit2"]


# ---------------------------------------------------------------------------
# Namespace.expect
# ---------------------------------------------------------------------------

class NamespaceExpectTest:
    def test_expect_sets_apidoc(self, ns):
        parser = ns.parser()

        @ns.expect(parser)
        def my_func():
            pass

        assert "expect" in my_func.__apidoc__
        assert len(my_func.__apidoc__["expect"]) == 1
        assert isinstance(my_func.__apidoc__["expect"][0], RequestParser)

    def test_expect_with_validate(self, ns):
        parser = ns.parser()

        @ns.expect(parser, validate=True)
        def my_func():
            pass

        assert my_func.__apidoc__["validate"] is True

    def test_expect_uses_namespace_validate(self):
        n = Namespace("myns", validate=True)
        parser = n.parser()

        @n.expect(parser)
        def my_func():
            pass

        assert my_func.__apidoc__["validate"] is True


# ---------------------------------------------------------------------------
# Namespace.parser
# ---------------------------------------------------------------------------

class NamespaceParserTest:
    def test_parser_returns_request_parser(self, ns):
        p = ns.parser()
        assert isinstance(p, RequestParser)

    def test_parser_returns_new_instance(self, ns):
        p1 = ns.parser()
        p2 = ns.parser()
        assert p1 is not p2


# ---------------------------------------------------------------------------
# Namespace.as_list
# ---------------------------------------------------------------------------

class NamespaceAsListTest:
    def test_as_list_sets_apidoc(self, ns):
        field = restx_fields.String()
        result = ns.as_list(field)
        assert result.__apidoc__["as_list"] is True
        assert result is field

    def test_as_list_merges_existing_apidoc(self, ns):
        field = restx_fields.String()
        field.__apidoc__ = {"description": "a field"}
        ns.as_list(field)
        assert field.__apidoc__["as_list"] is True
        assert field.__apidoc__["description"] == "a field"


# ---------------------------------------------------------------------------
# Namespace.marshal_with
# ---------------------------------------------------------------------------

class NamespaceMarshalWithTest:
    def test_marshal_with_sets_apidoc(self, app, ns):
        user_model = ns.model("User", {"name": restx_fields.String()})

        with app.app_context():
            @ns.marshal_with(user_model)
            def my_view():
                return {"name": "John"}

            assert "responses" in my_view.__apidoc__

    def test_marshal_with_as_list(self, app, ns):
        user_model = ns.model("UserList", {"name": restx_fields.String()})

        with app.app_context():
            @ns.marshal_with(user_model, as_list=True)
            def my_view():
                return [{"name": "John"}]

            resp_doc = list(my_view.__apidoc__["responses"].values())[0]
            assert isinstance(resp_doc[1], list)

    def test_marshal_with_custom_code(self, app, ns):
        user_model = ns.model("UserCreate", {"name": restx_fields.String()})

        with app.app_context():
            @ns.marshal_with(user_model, code=201)
            def my_view():
                return {"name": "John"}

            assert "201" in my_view.__apidoc__["responses"]


# ---------------------------------------------------------------------------
# Namespace.marshal_list_with
# ---------------------------------------------------------------------------

class NamespaceMarshalListWithTest:
    def test_marshal_list_with_sets_as_list(self, app, ns):
        user_model = ns.model("UserML", {"name": restx_fields.String()})

        with app.app_context():
            @ns.marshal_list_with(user_model)
            def my_view():
                return [{"name": "John"}]

            resp_doc = list(my_view.__apidoc__["responses"].values())[0]
            assert isinstance(resp_doc[1], list)


# ---------------------------------------------------------------------------
# Namespace.marshal
# ---------------------------------------------------------------------------

class NamespaceMarshalTest:
    def test_marshal_returns_dict(self, app, ns):
        user_model = ns.model("UserMarshal", {"name": restx_fields.String()})

        with app.app_context():
            result = ns.marshal({"name": "John", "extra": "ignored"}, user_model)
            assert result == {"name": "John"}


# ---------------------------------------------------------------------------
# Namespace.errorhandler
# ---------------------------------------------------------------------------

class NamespaceErrorHandlerTest:
    def test_errorhandler_registers_exception_handler(self, ns):
        class MyError(Exception):
            pass

        @ns.errorhandler(MyError)
        def handle_error(error):
            return {"message": str(error)}, 400

        assert MyError in ns.error_handlers
        assert ns.error_handlers[MyError] is handle_error

    def test_errorhandler_registers_default_handler(self, ns):
        def my_default_handler(error):
            return {"message": str(error)}, 500

        result = ns.errorhandler(my_default_handler)
        assert ns.default_error_handler is my_default_handler
        assert result is my_default_handler

    def test_errorhandler_wrapper_returns_func(self, ns):
        class MyError(Exception):
            pass

        def handler(error):
            pass

        wrapper = ns.errorhandler(MyError)
        result = wrapper(handler)
        assert result is handler


# ---------------------------------------------------------------------------
# Namespace.param
# ---------------------------------------------------------------------------

class NamespaceParamTest:
    def test_param_sets_apidoc(self, ns):
        @ns.param("name", "The name")
        def my_func():
            pass

        assert "params" in my_func.__apidoc__
        assert "name" in my_func.__apidoc__["params"]
        assert my_func.__apidoc__["params"]["name"]["description"] == "The name"

    def test_param_default_in_query(self, ns):
        @ns.param("name", "The name")
        def my_func():
            pass

        assert my_func.__apidoc__["params"]["name"]["in"] == "query"

    def test_param_custom_location(self, ns):
        @ns.param("token", "Auth token", _in="header")
        def my_func():
            pass

        assert my_func.__apidoc__["params"]["token"]["in"] == "header"


# ---------------------------------------------------------------------------
# Namespace.response
# ---------------------------------------------------------------------------

class NamespaceResponseTest:
    def test_response_sets_apidoc(self, ns):
        @ns.response(200, "Success")
        def my_func():
            pass

        assert "responses" in my_func.__apidoc__
        assert "200" in my_func.__apidoc__["responses"]

    def test_response_with_model(self, ns):
        user_model = ns.model("UserResp", {"name": restx_fields.String()})

        @ns.response(201, "Created", model=user_model)
        def my_func():
            pass

        code_doc = my_func.__apidoc__["responses"]["201"]
        assert "name" in code_doc[1]


# ---------------------------------------------------------------------------
# Namespace.header
# ---------------------------------------------------------------------------

class NamespaceHeaderTest:
    def test_header_sets_apidoc(self, ns):
        @ns.header("X-Custom", "A custom header")
        def my_func():
            pass

        assert "headers" in my_func.__apidoc__
        assert "X-Custom" in my_func.__apidoc__["headers"]
        assert my_func.__apidoc__["headers"]["X-Custom"]["description"] == "A custom header"

    def test_header_with_extra_kwargs(self, ns):
        @ns.header("X-Custom", "A custom header", required=True)
        def my_func():
            pass

        assert my_func.__apidoc__["headers"]["X-Custom"]["required"] is True


# ---------------------------------------------------------------------------
# Namespace.produces
# ---------------------------------------------------------------------------

class NamespaceProducesTest:
    def test_produces_sets_apidoc(self, ns):
        @ns.produces(["application/json"])
        def my_func():
            pass

        assert my_func.__apidoc__["produces"] == ["application/json"]


# ---------------------------------------------------------------------------
# Namespace.deprecated
# ---------------------------------------------------------------------------

class NamespaceDeprecatedTest:
    def test_deprecated_sets_apidoc(self, ns):
        @ns.deprecated
        def my_func():
            pass

        assert my_func.__apidoc__["deprecated"] is True


# ---------------------------------------------------------------------------
# Namespace.vendor
# ---------------------------------------------------------------------------

class NamespaceVendorTest:
    def test_vendor_with_kwargs(self, ns):
        @ns.vendor(**{"x-foo": "bar"})
        def my_func():
            pass

        assert my_func.__apidoc__["vendor"]["x-foo"] == "bar"

    def test_vendor_with_dict_arg(self, ns):
        @ns.vendor({"x-foo": "bar"})
        def my_func():
            pass

        assert my_func.__apidoc__["vendor"]["x-foo"] == "bar"

    def test_vendor_merges_args_and_kwargs(self, ns):
        @ns.vendor({"x-foo": "bar"}, **{"x-baz": "qux"})
        def my_func():
            pass

        assert my_func.__apidoc__["vendor"]["x-foo"] == "bar"
        assert my_func.__apidoc__["vendor"]["x-baz"] == "qux"


# ---------------------------------------------------------------------------
# Namespace.payload
# ---------------------------------------------------------------------------

class NamespacePayloadTest:
    def test_payload_returns_json(self, app, ns):
        with app.test_request_context(
            "/", method="POST", json={"key": "value"}
        ):
            payload = ns.payload
            assert payload == {"key": "value"}

    def test_payload_returns_none_for_no_json(self, app, ns):
        with app.test_request_context("/", content_type="application/json", data="null"):
            payload = ns.payload
            assert payload is None


# ---------------------------------------------------------------------------
# unshortcut_params_description
# ---------------------------------------------------------------------------

class UnshortcutParamsDescriptionTest:
    def test_expands_string_description(self):
        data = {"params": {"name": "a name param"}}
        unshortcut_params_description(data)
        assert data["params"]["name"] == {"description": "a name param"}

    def test_leaves_dict_description_intact(self):
        data = {"params": {"name": {"description": "already a dict"}}}
        unshortcut_params_description(data)
        assert data["params"]["name"] == {"description": "already a dict"}

    def test_no_params_key(self):
        data = {"other": "value"}
        unshortcut_params_description(data)
        assert "params" not in data

    def test_multiple_params(self):
        data = {"params": {"name": "a name", "id": "an id"}}
        unshortcut_params_description(data)
        assert data["params"]["name"] == {"description": "a name"}
        assert data["params"]["id"] == {"description": "an id"}


# ---------------------------------------------------------------------------
# handle_deprecations
# ---------------------------------------------------------------------------

class HandleDeprecationsTest:
    def test_parser_key_deprecated(self):
        doc = {"parser": "some_parser"}
        with pytest.warns(DeprecationWarning):
            handle_deprecations(doc)
        assert "parser" not in doc
        assert "some_parser" in doc["expect"]

    def test_body_key_deprecated(self):
        doc = {"body": "some_body"}
        with pytest.warns(DeprecationWarning):
            handle_deprecations(doc)
        assert "body" not in doc
        assert "some_body" in doc["expect"]

    def test_parser_key_merges_with_existing_expect(self):
        doc = {"parser": "new_parser", "expect": ["existing"]}
        with pytest.warns(DeprecationWarning):
            handle_deprecations(doc)
        assert "existing" in doc["expect"]
        assert "new_parser" in doc["expect"]

    def test_body_key_merges_with_existing_expect(self):
        doc = {"body": "new_body", "expect": ["existing"]}
        with pytest.warns(DeprecationWarning):
            handle_deprecations(doc)
        assert "existing" in doc["expect"]
        assert "new_body" in doc["expect"]

    def test_no_deprecations_needed(self):
        doc = {"description": "normal doc"}
        handle_deprecations(doc)
        assert doc == {"description": "normal doc"}
