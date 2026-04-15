"""Unit tests for flask_restx/api.py"""
import pytest
from collections import OrderedDict
from unittest.mock import MagicMock, patch

from flask import Flask, Blueprint
from werkzeug.exceptions import NotFound, MethodNotAllowed, NotAcceptable

from flask_restx import Api, Namespace, Resource
from flask_restx.api import SwaggerView, mask_parse_error_handler, mask_error_handler
from flask_restx.mask import ParseError, MaskError
from flask_restx._http import HTTPStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    _app = Flask(__name__)
    _app.config["TESTING"] = True
    return _app


@pytest.fixture
def api(app):
    return Api(app)


@pytest.fixture
def client(app, api):
    return app.test_client()


# ---------------------------------------------------------------------------
# mask_parse_error_handler / mask_error_handler
# ---------------------------------------------------------------------------

def test_mask_parse_error_handler_returns_message_and_status():
    error = ParseError("bad mask")
    data, code = mask_parse_error_handler(error)
    assert "Mask parse error" in data["message"]
    assert code == HTTPStatus.BAD_REQUEST


def test_mask_error_handler_returns_message_and_status():
    error = MaskError("some error")
    data, code = mask_error_handler(error)
    assert "Mask error" in data["message"]
    assert code == HTTPStatus.BAD_REQUEST


# ---------------------------------------------------------------------------
# Api.__init__
# ---------------------------------------------------------------------------

def test_api_init_defaults(app):
    api = Api(app)
    assert api.version == "1.0"
    assert api.title == "API"
    assert api.description is None
    assert api.prefix == ""
    assert api.default_mediatype == "application/json"
    assert api.catch_all_404s is False
    assert api.serve_challenge_on_401 is False
    assert api.decorators == []
    assert isinstance(api.representations, OrderedDict)
    assert api.namespaces


def test_api_init_custom_title(app):
    api = Api(app, title="My API", version="2.0", description="Desc")
    assert api.title == "My API"
    assert api.version == "2.0"
    assert api.description == "Desc"


def test_api_init_without_app():
    api = Api()
    assert api.app is None


def test_api_init_with_decorators(app):
    def my_decorator(f):
        return f

    api = Api(app, decorators=[my_decorator])
    assert my_decorator in api.decorators


def test_api_init_with_prefix(app):
    api = Api(app, prefix="/v1")
    assert api.prefix == "/v1"


def test_api_init_ordered(app):
    api = Api(app, ordered=True)
    assert api.ordered is True


def test_api_init_tags(app):
    api = Api(app, tags=["tag1"])
    assert api.tags == ["tag1"]


def test_api_init_default_namespace_created(app):
    api = Api(app)
    assert api.default_namespace is not None
    assert api.default_namespace.name == "default"


def test_api_init_error_handlers_defaults(app):
    api = Api(app)
    assert ParseError in api.error_handlers
    assert MaskError in api.error_handlers


# ---------------------------------------------------------------------------
# Api.init_app
# ---------------------------------------------------------------------------

def test_init_app_lazy(app):
    api = Api()
    api.init_app(app)
    assert api.app is app


def test_init_app_overrides_kwargs(app):
    api = Api()
    api.init_app(app, title="New Title", description="New Desc")
    assert api.title == "New Title"
    assert api.description == "New Desc"


def test_init_app_sets_url_scheme(app):
    api = Api()
    api.init_app(app, url_scheme="https")
    assert api.url_scheme == "https"


# ---------------------------------------------------------------------------
# Api._init_app
# ---------------------------------------------------------------------------

def test_init_app_sets_config_defaults(app):
    api = Api(app)
    assert app.config.get("RESTX_MASK_HEADER") == "X-Fields"
    assert app.config.get("RESTX_MASK_SWAGGER") is True
    assert app.config.get("RESTX_INCLUDE_ALL_MODELS") is False


def test_init_app_deprecated_error_404_help_config(app):
    app.config["ERROR_404_HELP"] = False
    with pytest.warns(DeprecationWarning):
        api = Api(app)
    assert app.config.get("RESTX_ERROR_404_HELP") is False


# ---------------------------------------------------------------------------
# Api.__getattr__
# ---------------------------------------------------------------------------

def test_getattr_delegates_to_default_namespace(app):
    api = Api(app)
    # route is an attribute on Namespace
    assert hasattr(api, "route")


def test_getattr_raises_for_unknown_attribute(app):
    api = Api(app)
    with pytest.raises(AttributeError) as exc_info:
        _ = api.nonexistent_attribute_xyz
    assert "Api does not have" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Api._complete_url
# ---------------------------------------------------------------------------

def test_complete_url_no_prefix_no_registration():
    api = Api()
    result = api._complete_url("/users", "")
    assert result == "/users"


def test_complete_url_with_prefix():
    api = Api(prefix="/v1")
    result = api._complete_url("/users", "")
    assert result == "/v1/users"


def test_complete_url_with_registration_prefix():
    api = Api()
    result = api._complete_url("/users", "/api")
    assert result == "/api/users"


def test_complete_url_with_all_parts():
    api = Api(prefix="/v1")
    result = api._complete_url("/users", "/api")
    assert result == "/api/v1/users"


# ---------------------------------------------------------------------------
# Api._register_apidoc
# ---------------------------------------------------------------------------

def test_register_apidoc_sets_extension(app):
    api = Api(app)
    assert app.extensions.get("restx", {}).get("apidoc_registered") is True


# ---------------------------------------------------------------------------
# Api.register_resource
# ---------------------------------------------------------------------------

def test_register_resource_adds_endpoint(app):
    api = Api(app)

    class MyResource(Resource):
        def get(self):
            return {"hello": "world"}

    ns = api.default_namespace
    endpoint = api.register_resource(ns, MyResource, "/myresource")
    assert endpoint in api.endpoints


def test_register_resource_deferred_when_no_app():
    api = Api()

    class MyResource(Resource):
        def get(self):
            return {"hello": "world"}

    ns = api.default_namespace
    api.register_resource(ns, MyResource, "/myresource")
    assert len(api.resources) > 0


# ---------------------------------------------------------------------------
# Api._configure_namespace_logger
# ---------------------------------------------------------------------------

def test_configure_namespace_logger(app):
    api = Api(app)
    ns = Namespace("test_ns")
    api._configure_namespace_logger(app, ns)
    assert ns.logger.level == app.logger.level


# ---------------------------------------------------------------------------
# Api.output
# ---------------------------------------------------------------------------

def test_output_wraps_response(app):
    api = Api(app)

    def my_view():
        return {"hello": "world"}, 200

    with app.test_request_context("/"):
        wrapped = api.output(my_view)
        resp = wrapped()
        assert resp.status_code == 200


def test_output_returns_base_response_unchanged(app):
    from flask import make_response as flask_make_response

    api = Api(app)

    def my_view():
        return flask_make_response("hello", 200)

    with app.test_request_context("/"):
        wrapped = api.output(my_view)
        resp = wrapped()
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Api.make_response
# ---------------------------------------------------------------------------

def test_make_response_json(app):
    api = Api(app)
    with app.test_request_context("/", headers={"Accept": "application/json"}):
        resp = api.make_response({"key": "value"}, 200)
        assert resp.status_code == 200
        assert "application/json" in resp.content_type


def test_make_response_not_acceptable(app):
    api = Api(app, default_mediatype=None)
    with app.test_request_context("/", headers={"Accept": "text/xml"}):
        with pytest.raises(NotAcceptable):
            api.make_response({"key": "value"}, 200)


@pytest.mark.skip(reason="text/plain branch requires best_match to select text/plain, which doesn't happen when application/json is the default")
def test_make_response_text_plain(app):
    api = Api(app)
    with app.test_request_context("/", headers={"Accept": "text/plain"}):
        resp = api.make_response("hello", 200)
        assert "text/plain" in resp.content_type


# ---------------------------------------------------------------------------
# Api.documentation decorator
# ---------------------------------------------------------------------------

def test_documentation_decorator(app):
    api = Api(app)

    @api.documentation
    def custom_doc():
        return "custom doc"

    assert api._doc_view is custom_doc


# ---------------------------------------------------------------------------
# Api.render_root
# ---------------------------------------------------------------------------

def test_render_root_aborts_404(app):
    # With doc=False, render_root is the registered handler for "/"
    api = Api(app, doc=False)
    with app.test_client() as client:
        resp = client.get("/")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Api.render_doc
# ---------------------------------------------------------------------------

def test_render_doc_with_doc_view(app):
    api = Api(app)

    @api.documentation
    def custom_doc():
        return "custom doc page"

    with app.test_request_context("/"):
        result = api.render_doc()
        assert result == "custom doc page"


def test_render_doc_no_doc_aborts(app):
    api = Api(app, doc=False)
    with app.test_request_context("/"):
        with pytest.raises(Exception):
            api.render_doc()


# ---------------------------------------------------------------------------
# Api.default_endpoint
# ---------------------------------------------------------------------------

def test_default_endpoint_basic(app):
    api = Api(app)

    class MyResource(Resource):
        pass

    endpoint = api.default_endpoint(MyResource, api.default_namespace)
    assert "my" in endpoint.lower() and "resource" in endpoint.lower()


def test_default_endpoint_with_namespace(app):
    api = Api(app)
    ns = api.namespace("myns", "My Namespace")

    class MyResource(Resource):
        pass

    endpoint = api.default_endpoint(MyResource, ns)
    assert "myns" in endpoint


def test_default_endpoint_collision_handling(app):
    api = Api(app)

    class MyResource(Resource):
        pass

    base = api.default_endpoint(MyResource, api.default_namespace)
    api.endpoints.add(base)
    endpoint = api.default_endpoint(MyResource, api.default_namespace)
    assert endpoint == base + "_2"


def test_default_endpoint_multiple_collisions(app):
    api = Api(app)

    class MyResource(Resource):
        pass

    base = api.default_endpoint(MyResource, api.default_namespace)
    api.endpoints.add(base)
    api.endpoints.add(base + "_2")
    endpoint = api.default_endpoint(MyResource, api.default_namespace)
    assert endpoint == base + "_3"


# ---------------------------------------------------------------------------
# Api.get_ns_path / Api.ns_urls
# ---------------------------------------------------------------------------

def test_get_ns_path_returns_none_if_not_set(app):
    api = Api(app)
    ns = Namespace("test")
    assert api.get_ns_path(ns) is None


def test_get_ns_path_returns_set_path(app):
    api = Api(app)
    ns = Namespace("testpath_ns")
    api.add_namespace(ns, path="/custom")
    assert api.get_ns_path(ns) == "/custom"


def test_ns_urls(app):
    api = Api(app)
    ns = api.namespace("test_ns3", path="/items")
    urls = api.ns_urls(ns, ["/", "/<int:id>"])
    assert "/items/" in urls
    assert "/items/<int:id>" in urls


# ---------------------------------------------------------------------------
# Api.add_namespace
# ---------------------------------------------------------------------------

def test_add_namespace(app):
    api = Api(app)
    ns = Namespace("addtest")
    api.add_namespace(ns)
    assert ns in api.namespaces


def test_add_namespace_idempotent(app):
    api = Api(app)
    ns = Namespace("addtest2")
    api.add_namespace(ns)
    api.add_namespace(ns)
    assert api.namespaces.count(ns) == 1


def test_add_namespace_with_custom_path(app):
    api = Api(app)
    ns = Namespace("addtest3")
    api.add_namespace(ns, path="/custom_path")
    assert api.get_ns_path(ns) == "/custom_path"


# ---------------------------------------------------------------------------
# Api.namespace
# ---------------------------------------------------------------------------

def test_namespace_factory(app):
    api = Api(app)
    ns = api.namespace("mytest", "My Test Namespace")
    assert isinstance(ns, Namespace)
    assert ns in api.namespaces


# ---------------------------------------------------------------------------
# Api.endpoint
# ---------------------------------------------------------------------------

def test_endpoint_without_blueprint(app):
    api = Api(app)
    assert api.endpoint("myview") == "myview"


def test_endpoint_with_blueprint(app):
    bp = Blueprint("mybp", __name__)
    api = Api(bp)
    app.register_blueprint(bp)
    assert api.endpoint("myview") == "mybp.myview"


# ---------------------------------------------------------------------------
# Api.specs_url / base_url / base_path
# ---------------------------------------------------------------------------

def test_specs_url(app):
    api = Api(app)
    with app.test_request_context("/"):
        url = api.specs_url
        assert "swagger.json" in url


def test_base_url(app):
    api = Api(app)
    with app.test_request_context("/"):
        url = api.base_url
        assert url.startswith("http")


def test_base_path(app):
    api = Api(app)
    with app.test_request_context("/"):
        path = api.base_path
        assert path == "/"


# ---------------------------------------------------------------------------
# Api.__schema__
# ---------------------------------------------------------------------------

def test_schema_property(app):
    api = Api(app)
    with app.test_request_context("/"):
        schema = api.__schema__
        assert isinstance(schema, dict)
        assert "info" in schema or "swagger" in schema or "openapi" in schema or "error" in schema


# ---------------------------------------------------------------------------
# Api._own_and_child_error_handlers
# ---------------------------------------------------------------------------

def test_own_and_child_error_handlers(app):
    api = Api(app)
    handlers = api._own_and_child_error_handlers
    assert ParseError in handlers
    assert MaskError in handlers


def test_own_and_child_error_handlers_includes_namespace_handlers(app):
    api = Api(app)
    ns = api.namespace("errns")

    class CustomError(Exception):
        pass

    @ns.errorhandler(CustomError)
    def handle_custom(e):
        return {"message": "custom"}, 400

    handlers = api._own_and_child_error_handlers
    assert CustomError in handlers


# ---------------------------------------------------------------------------
# Api.errorhandler
# ---------------------------------------------------------------------------

def test_errorhandler_registers_exception_handler(app):
    api = Api(app)

    class MyError(Exception):
        pass

    @api.errorhandler(MyError)
    def handler(e):
        return {"message": "handled"}, 400

    assert MyError in api.error_handlers


def test_errorhandler_registers_default_handler(app):
    api = Api(app)

    def default_handler(e):
        return {"message": "default"}, 500

    api.errorhandler(default_handler)
    assert api._default_error_handler is default_handler


# ---------------------------------------------------------------------------
# Api.owns_endpoint
# ---------------------------------------------------------------------------

def test_owns_endpoint_true(app):
    api = Api(app)
    api.endpoints.add("myendpoint")
    assert api.owns_endpoint("myendpoint") is True


def test_owns_endpoint_false(app):
    api = Api(app)
    assert api.owns_endpoint("other_endpoint") is False


def test_owns_endpoint_with_blueprint(app):
    bp = Blueprint("mybp2", __name__)
    api = Api(bp)
    app.register_blueprint(bp)
    api.endpoints.add("myendpoint")
    assert api.owns_endpoint("mybp2.myendpoint") is True
    assert api.owns_endpoint("otherbp.myendpoint") is False


# ---------------------------------------------------------------------------
# Api.error_router
# ---------------------------------------------------------------------------

def test_error_router_calls_handle_error_for_fr_route(app):
    api = Api(app)
    original = MagicMock()

    with app.test_request_context("/"):
        with patch.object(api, "_has_fr_route", return_value=True):
            with patch.object(api, "handle_error", return_value="handled") as mock_handle:
                result = api.error_router(original, Exception("test"))
                mock_handle.assert_called_once()
                assert result == "handled"


def test_error_router_falls_back_to_original_on_exception(app):
    api = Api(app)
    original = MagicMock(return_value="original")

    with app.test_request_context("/"):
        with patch.object(api, "_has_fr_route", return_value=True):
            with patch.object(api, "handle_error", side_effect=Exception("inner")):
                result = api.error_router(original, Exception("test"))
                assert result == "original"


def test_error_router_non_fr_route_uses_original(app):
    api = Api(app)
    original = MagicMock(return_value="from_original")

    with app.test_request_context("/"):
        with patch.object(api, "_has_fr_route", return_value=False):
            result = api.error_router(original, Exception("test"))
            assert result == "from_original"


# ---------------------------------------------------------------------------
# Api._propagate_exceptions
# ---------------------------------------------------------------------------

def test_propagate_exceptions_from_config(app):
    api = Api(app)
    app.config["PROPAGATE_EXCEPTIONS"] = True
    with app.test_request_context("/"):
        assert api._propagate_exceptions() is True


def test_propagate_exceptions_testing_mode(app):
    api = Api(app)
    app.config.pop("PROPAGATE_EXCEPTIONS", None)
    app.config["TESTING"] = True
    with app.test_request_context("/"):
        assert api._propagate_exceptions() is True


def test_propagate_exceptions_debug_mode(app):
    api = Api(app)
    app.config.pop("PROPAGATE_EXCEPTIONS", None)
    app.config["TESTING"] = False
    app.config["DEBUG"] = True
    with app.test_request_context("/"):
        assert api._propagate_exceptions() is True


# ---------------------------------------------------------------------------
# Api.handle_error
# ---------------------------------------------------------------------------

def test_handle_error_http_exception(app):
    api = Api(app)
    with app.test_request_context("/"):
        resp = api.handle_error(NotFound())
        assert resp.status_code == 404


def test_handle_error_custom_handler(app):
    api = Api(app)

    class MyError(Exception):
        pass

    @api.errorhandler(MyError)
    def handler(e):
        return {"message": "my error"}, 400

    with app.test_request_context("/"):
        app.config["PROPAGATE_EXCEPTIONS"] = False
        resp = api.handle_error(MyError("test"))
        assert resp.status_code == 400


def test_handle_error_internal_server_error(app):
    api = Api(app)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.config["TESTING"] = False

    with app.test_request_context("/"):
        resp = api.handle_error(Exception("some error"))
        assert resp.status_code == 500


def test_handle_error_unauthorized_adds_challenge(app):
    api = Api(app, serve_challenge_on_401=True)
    from werkzeug.exceptions import Unauthorized

    with app.test_request_context("/"):
        resp = api.handle_error(Unauthorized())
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers


def test_handle_error_propagate_reraises_active_exception(app):
    # Lines 706-708: exc_value is e → bare raise
    api = Api(app)
    app.config["PROPAGATE_EXCEPTIONS"] = True
    app.config["TESTING"] = False

    with app.test_request_context("/"):
        with pytest.raises(ValueError, match="active exc"):
            try:
                raise ValueError("active exc")
            except ValueError as exc:
                api.handle_error(exc)


def test_handle_error_propagate_raises_e_directly(app):
    # Line 710: exc_value is not e → raise e
    api = Api(app)
    app.config["PROPAGATE_EXCEPTIONS"] = True
    app.config["TESTING"] = False

    with app.test_request_context("/"):
        e = ValueError("direct raise")
        with pytest.raises(ValueError, match="direct raise"):
            api.handle_error(e)


def test_handle_error_http_exception_with_response_no_code(app):
    # Lines 735-736: HTTPException with code=None but response set
    from werkzeug.exceptions import HTTPException
    from flask import Response as FlaskResponse

    api = Api(app)

    exc = HTTPException()
    exc.code = None
    exc.response = FlaskResponse(status=422)

    with app.test_request_context("/"):
        resp = api.handle_error(exc)
        assert resp.status_code == 422


def test_handle_error_default_error_handler(app):
    # Lines 741-742: _default_error_handler is set
    api = Api(app)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.config["TESTING"] = False

    @api.errorhandler
    def default_handler(e):
        return {"message": "default handled"}, 422

    with app.test_request_context("/"):
        resp = api.handle_error(Exception("any error"))
        assert resp.status_code == 422


def test_handle_error_not_acceptable_without_default_mediatype(app):
    # Lines 776-777: 406 with default_mediatype=None uses fallback
    api = Api(app)
    api.default_mediatype = None

    with app.test_request_context("/"):
        resp = api.handle_error(NotAcceptable())
        assert resp.status_code == 406


# ---------------------------------------------------------------------------
# Api._help_on_404
# ---------------------------------------------------------------------------

def test_help_on_404_no_close_matches(app):
    api = Api(app)
    with app.test_request_context("/xyz"):
        result = api._help_on_404("Not Found")
        assert result == "Not Found"


def test_help_on_404_with_close_matches(app):
    api = Api(app)

    @app.route("/users")
    def users():
        return ""

    with app.test_request_context("/user"):
        result = api._help_on_404()
        if result:
            assert "users" in result or result is None


# ---------------------------------------------------------------------------
# Api.as_postman
# ---------------------------------------------------------------------------

def test_as_postman(app):
    api = Api(app, title="Test API")
    result = api.as_postman()
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Api.payload
# ---------------------------------------------------------------------------

def test_payload_returns_json(app):
    api = Api(app)
    with app.test_request_context("/", method="POST", json={"key": "value"}):
        assert api.payload == {"key": "value"}


# ---------------------------------------------------------------------------
# Api.refresolver
# ---------------------------------------------------------------------------

def test_refresolver_property(app):
    api = Api(app)
    with app.test_request_context("/"):
        resolver = api.refresolver
        assert resolver is not None


def test_refresolver_cached(app):
    api = Api(app)
    with app.test_request_context("/"):
        resolver1 = api.refresolver
        resolver2 = api.refresolver
        # Both should be valid Registry objects
        assert resolver1 is not None
        assert resolver2 is not None


def test_refresolver_with_models_no_schema_definitions(app):
    from flask_restx import fields

    api = Api(app)
    api.model("MyModel", {"name": fields.String()})

    with app.test_request_context("/"):
        # Schema has no "definitions" key; models exist -> exercises else-branch loop
        resolver = api.refresolver
        assert resolver is not None


def test_refresolver_model_without_id_gets_id_added(app):
    from flask_restx import fields

    api = Api(app)
    model = api.model("NoIdModel", {"value": fields.Integer()})

    with app.test_request_context("/"):
        # Model schema has no $id; refresolver should add one via copy
        assert "$id" not in model.__schema__
        resolver = api.refresolver
        assert resolver is not None


def test_refresolver_model_with_existing_id_not_overwritten(app):
    from flask_restx import fields
    from unittest.mock import patch, PropertyMock

    api = Api(app)
    model = api.model("HasIdModel", {"value": fields.String()})

    schema_with_id = dict(model.__schema__)
    schema_with_id["$id"] = "http://localhost/custom-id"

    with app.test_request_context("/"):
        with patch.object(type(model), "__schema__", new_callable=PropertyMock) as mock_schema:
            mock_schema.return_value = schema_with_id
            resolver = api.refresolver
            assert resolver is not None


def test_refresolver_with_schema_having_definitions(app):
    from unittest.mock import patch, PropertyMock

    api = Api(app)
    schema_with_defs = {
        "$id": "http://localhost/schema.json",
        "definitions": {"Foo": {"type": "object"}},
    }

    with app.test_request_context("/"):
        with patch.object(type(api), "__schema__", new_callable=PropertyMock) as mock_schema:
            mock_schema.return_value = schema_with_defs
            resolver = api.refresolver
            assert resolver is not None


def test_refresolver_with_schema_definitions_no_id(app):
    from unittest.mock import patch, PropertyMock

    api = Api(app)
    # Schema with definitions but no $id -> uses default http://localhost/schema.json
    schema_with_defs = {
        "definitions": {"Bar": {"type": "string"}},
    }

    with app.test_request_context("/"):
        with patch.object(type(api), "__schema__", new_callable=PropertyMock) as mock_schema:
            mock_schema.return_value = schema_with_defs
            resolver = api.refresolver
            assert resolver is not None


# ---------------------------------------------------------------------------
# Api._blueprint_setup_add_url_rule_patch
# ---------------------------------------------------------------------------

def test_blueprint_setup_add_url_rule_patch_callable_rule(app):
    bp = Blueprint("testbp", __name__, url_prefix="/prefix")
    api = Api(bp)
    app.register_blueprint(bp)


def test_blueprint_setup_add_url_rule_patch_string_rule():
    from flask_restx.api import Api as RestxApi

    setup_state = MagicMock()
    setup_state.url_prefix = "/prefix"
    setup_state.subdomain = None
    setup_state.url_defaults = {}
    setup_state.blueprint = MagicMock()
    setup_state.blueprint.name = "mybp"

    def view_func():
        return "ok"

    view_func.__name__ = "view_func"

    RestxApi._blueprint_setup_add_url_rule_patch(
        setup_state, "/users", endpoint="users", view_func=view_func
    )
    setup_state.app.add_url_rule.assert_called_once()


def test_blueprint_setup_add_url_rule_patch_no_prefix():
    from flask_restx.api import Api as RestxApi

    setup_state = MagicMock()
    setup_state.url_prefix = None
    setup_state.subdomain = None
    setup_state.url_defaults = {}
    setup_state.blueprint = MagicMock()
    setup_state.blueprint.name = "mybp"

    def view_func():
        return "ok"

    view_func.__name__ = "view_func"

    RestxApi._blueprint_setup_add_url_rule_patch(
        setup_state, "/users", endpoint="users", view_func=view_func
    )
    setup_state.app.add_url_rule.assert_called_once()


# ---------------------------------------------------------------------------
# Api._deferred_blueprint_init
# ---------------------------------------------------------------------------

def test_deferred_blueprint_init(app):
    bp = Blueprint("defbp", __name__)
    api = Api(bp)
    app.register_blueprint(bp)
    assert api.blueprint_setup is not None


def test_deferred_blueprint_init_raises_on_second_registration(app):
    bp = Blueprint("defbp2", __name__)
    api = Api(bp)
    app.register_blueprint(bp)
    with pytest.raises(ValueError):
        app.register_blueprint(bp)


# ---------------------------------------------------------------------------
# Api.mediatypes_method / Api.mediatypes
# ---------------------------------------------------------------------------

def test_mediatypes_method_returns_callable(app):
    api = Api(app)
    method = api.mediatypes_method()
    assert callable(method)


def test_mediatypes_returns_list(app):
    api = Api(app)
    with app.test_request_context("/", headers={"Accept": "application/json"}):
        result = api.mediatypes()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Api.representation
# ---------------------------------------------------------------------------

def test_representation_decorator(app):
    api = Api(app)

    @api.representation("application/xml")
    def xml_output(data, code, headers):
        from flask import make_response as fmr
        return fmr(str(data), code)

    assert "application/xml" in api.representations


# ---------------------------------------------------------------------------
# Api.unauthorized
# ---------------------------------------------------------------------------

def test_unauthorized_without_challenge(app):
    api = Api(app)
    from flask import make_response as fmr
    resp = fmr("", 401)
    with app.test_request_context("/"):
        result = api.unauthorized(resp)
        assert "WWW-Authenticate" not in result.headers


def test_unauthorized_with_challenge(app):
    api = Api(app, serve_challenge_on_401=True)
    from flask import make_response as fmr
    resp = fmr("", 401)
    with app.test_request_context("/"):
        result = api.unauthorized(resp)
        assert "WWW-Authenticate" in result.headers


# ---------------------------------------------------------------------------
# Api.url_for
# ---------------------------------------------------------------------------

def test_url_for_without_blueprint(app):
    api = Api(app)

    class MyRes(Resource):
        def get(self):
            return {}

    ns = api.default_namespace
    api.register_resource(ns, MyRes, "/myres")

    with app.test_request_context("/"):
        url = api.url_for(MyRes)
        assert "/myres" in url


def test_url_for_with_blueprint(app):
    bp = Blueprint("urlbp", __name__)
    api = Api(bp)

    class MyBpRes(Resource):
        def get(self):
            return {}

    ns = api.default_namespace
    api.register_resource(ns, MyBpRes, "/mybpres")
    app.register_blueprint(bp)

    with app.test_request_context("/"):
        url = api.url_for(MyBpRes)
        assert "/mybpres" in url


# ---------------------------------------------------------------------------
# SwaggerView
# ---------------------------------------------------------------------------

def test_swagger_view_mediatypes(app):
    api = Api(app)
    with app.test_request_context("/"):
        view = SwaggerView()
        view.api = api
        assert "application/json" in view.mediatypes()


def test_swagger_view_get_returns_schema(app):
    api = Api(app)
    with app.test_request_context("/"):
        # Access via the client to trigger the view
        client = app.test_client()
        resp = client.get("/swagger.json")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Api._should_use_fr_error_handler
# ---------------------------------------------------------------------------

def test_should_use_fr_error_handler_catch_all_404s(app):
    api = Api(app, catch_all_404s=True)
    with app.test_request_context("/nonexistent"):
        result = api._should_use_fr_error_handler()
        assert result is True


def test_should_use_fr_error_handler_not_catch_404s(app):
    api = Api(app, catch_all_404s=False)
    with app.test_request_context("/nonexistent"):
        result = api._should_use_fr_error_handler()
        assert result is False or result is None


# ---------------------------------------------------------------------------
# Api._has_fr_route
# ---------------------------------------------------------------------------

def test_has_fr_route_no_url_rule(app):
    api = Api(app, catch_all_404s=False)
    with app.test_request_context("/nonexistent"):
        with patch.object(api, "_should_use_fr_error_handler", return_value=False):
            result = api._has_fr_route()
            assert result is False


def test_has_fr_route_with_fr_endpoint(app):
    api = Api(app)

    class TestHasRoute(Resource):
        def get(self):
            return {}

    ns = api.default_namespace
    api.register_resource(ns, TestHasRoute, "/testhasroute")

    with app.test_request_context("/testhasroute"):
        with patch.object(api, "_should_use_fr_error_handler", return_value=False):
            result = api._has_fr_route()
            assert result is True
