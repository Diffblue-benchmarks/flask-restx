# -*- coding: utf-8 -*-
import pytest
from flask import Flask
from flask_restx import Api, Resource, Namespace
from flask_restx.postman import clean, Request, Folder, PostmanCollectionV1


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def simple_api(app):
    api = Api(app, title="Test API", version="1.0", description="A test API")
    return api, app


@pytest.fixture
def api_with_namespace(app):
    api = Api(app, title="Test API", version="1.0", description="A test API")
    ns = api.namespace("pets", description="Pet operations")

    @ns.route("/")
    class PetList(Resource):
        def get(self):
            pass

        def post(self):
            pass

    @ns.route("/<int:pet_id>")
    @ns.param("pet_id", "The pet identifier")
    class Pet(Resource):
        def get(self, pet_id):
            pass

    return api, app


# Tests for clean()

def test_clean_removes_none_values():
    result = clean({"a": 1, "b": None, "c": "hello"})
    assert result == {"a": 1, "c": "hello"}


def test_clean_keeps_all_when_no_none():
    result = clean({"a": 1, "b": 2})
    assert result == {"a": 1, "b": 2}


def test_clean_returns_empty_for_all_none():
    result = clean({"a": None, "b": None})
    assert result == {}


# Tests for Request

def test_request_init(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        req = Request(col, "/test", [], "get", {"operationId": "test_op"})
        assert req.path == "/test"
        assert req.method == "GET"
        assert req.params == []
        assert req.operation == {"operationId": "test_op"}
        assert req.collection is col


def test_request_method_uppercased(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        req = Request(col, "/test", [], "post", {"operationId": "test_op"})
        assert req.method == "POST"


def test_request_url(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        req = Request(col, "/mypath", [], "get", {"operationId": "test_op"})
        assert req.url == "http://localhost/mypath"


def test_request_url_strips_trailing_slash(app):
    api = Api(app, title="T", version="1.0")
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        req = Request(col, "/path", [], "get", {"operationId": "op"})
        url = req.url
        # base_url ends with / which is stripped before joining
        assert url.endswith("/path")


def test_request_id_is_string(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        req = Request(col, "/test", [], "get", {"operationId": "test_op"})
        rid = req.id
        assert isinstance(rid, str)
        assert len(rid) == 36  # UUID format


def test_request_id_deterministic(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        req1 = Request(col, "/test", [], "get", {"operationId": "op"})
        req2 = Request(col, "/test", [], "get", {"operationId": "op"})
        assert req1.id == req2.id


def test_request_headers_get_no_content_type(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        req = Request(col, "/test", [], "get", {"operationId": "op"})
        assert "Content-Type" not in req.headers


def test_request_headers_post_with_consumes(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        operation = {"operationId": "op", "consumes": ["application/json"]}
        req = Request(col, "/test", [], "post", operation)
        assert "Content-Type:application/json" in req.headers


def test_request_headers_uses_operation_consumes_over_global(app):
    api = Api(app, title="T", version="1.0")
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        operation = {
            "operationId": "op",
            "consumes": ["application/xml"],
        }
        req = Request(col, "/test", [], "put", operation)
        assert "Content-Type:application/xml" in req.headers


def test_request_headers_includes_header_param(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        operation = {
            "operationId": "op",
            "parameters": [{"in": "header", "name": "X-Token", "default": "abc"}],
        }
        req = Request(col, "/test", [], "get", operation)
        assert "X-Token:abc" in req.headers


def test_request_headers_header_param_no_default(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        operation = {
            "operationId": "op",
            "parameters": [{"in": "header", "name": "X-Token"}],
        }
        req = Request(col, "/test", [], "get", operation)
        assert "X-Token:" in req.headers


def test_request_headers_with_global_security(app):
    api = Api(app, title="T", version="1.0")
    with app.test_request_context():
        # Inject security into schema
        schema = api.__schema__
        schema["security"] = [{"mykey": []}]
        schema["securityDefinitions"] = {
            "mykey": {"in": "header", "name": "X-Api-Key", "type": "apiKey"}
        }
        col = PostmanCollectionV1(api)
        operation = {"operationId": "op"}
        req = Request(col, "/test", [], "get", operation)
        assert "X-Api-Key:" in req.headers


def test_request_headers_with_operation_security(app):
    api = Api(app, title="T", version="1.0")
    with app.test_request_context():
        schema = api.__schema__
        schema["securityDefinitions"] = {
            "apikey": {"in": "header", "name": "X-Api-Key", "type": "apiKey"}
        }
        col = PostmanCollectionV1(api)
        operation = {"operationId": "op", "security": [{"apikey": []}]}
        req = Request(col, "/test", [], "get", operation)
        assert "X-Api-Key:" in req.headers


def test_request_folder_no_tags(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        req = Request(col, "/test", [], "get", {"operationId": "op"})
        assert req.folder is None


def test_request_folder_empty_tags(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        req = Request(col, "/test", [], "get", {"operationId": "op", "tags": []})
        assert req.folder is None


def test_request_folder_matching_tag(api_with_namespace):
    api, app = api_with_namespace
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        req = Request(col, "/test", [], "get", {"operationId": "op", "tags": ["pets"]})
        folder_id = req.folder
        assert folder_id is not None
        assert isinstance(folder_id, str)


def test_request_folder_no_matching_tag(api_with_namespace):
    api, app = api_with_namespace
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        req = Request(col, "/test", [], "get", {"operationId": "op", "tags": ["nonexistent"]})
        assert req.folder is None


def test_request_as_dict_basic(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        operation = {"operationId": "list_items", "summary": "List items"}
        req = Request(col, "/items", [], "get", operation)
        d = req.as_dict()
        assert d["method"] == "GET"
        assert d["name"] == "list_items"
        assert d["description"] == "List items"
        assert "id" in d
        assert "url" in d
        assert "collectionId" in d
        assert "time" in d


def test_request_as_dict_no_summary_excluded(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        operation = {"operationId": "list_items"}
        req = Request(col, "/items", [], "get", operation)
        d = req.as_dict()
        assert "description" not in d


def test_request_process_url_no_params(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        req = Request(col, "/items", [], "get", {"operationId": "op"})
        url, pvars = req.process_url()
        assert url == "http://localhost/items"
        assert pvars is None


def test_request_process_url_with_path_params(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        params = [{"in": "path", "name": "item_id", "type": "integer"}]
        req = Request(col, "/items/{item_id}", params, "get", {"operationId": "op"})
        url, pvars = req.process_url()
        assert ":item_id" in url
        assert pvars == {"item_id": 0}


def test_request_process_url_with_string_path_param(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        params = [{"in": "path", "name": "name", "type": "string"}]
        req = Request(col, "/items/{name}", params, "get", {"operationId": "op"})
        url, pvars = req.process_url()
        assert ":name" in url
        assert pvars == {"name": ""}


def test_request_process_url_with_query_params_urlvars_false(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        operation = {
            "operationId": "op",
            "parameters": [{"in": "query", "name": "q", "type": "string"}],
        }
        req = Request(col, "/items", [], "get", operation)
        url, pvars = req.process_url(urlvars=False)
        assert "?" not in url


def test_request_process_url_with_query_params_urlvars_true(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        operation = {
            "operationId": "op",
            "parameters": [{"in": "query", "name": "q", "type": "string"}],
        }
        req = Request(col, "/items", [], "get", operation)
        url, pvars = req.process_url(urlvars=True)
        assert "?" in url
        assert "q=" in url


def test_request_process_url_operation_params_override(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        operation = {
            "operationId": "op",
            "parameters": [{"in": "path", "name": "id", "type": "number"}],
        }
        req = Request(col, "/items/{id}", [], "get", operation)
        url, pvars = req.process_url()
        assert ":id" in url
        assert pvars == {"id": 0}


# Tests for Folder

def test_folder_init(api_with_namespace):
    api, app = api_with_namespace
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        tag = {"name": "pets", "description": "Pet operations"}
        folder = Folder(col, tag)
        assert folder.tag == "pets"
        assert folder.description == "Pet operations"
        assert folder.collection is col


def test_folder_id_is_string(api_with_namespace):
    api, app = api_with_namespace
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        tag = {"name": "pets", "description": "Pet operations"}
        folder = Folder(col, tag)
        assert isinstance(folder.id, str)
        assert len(folder.id) == 36


def test_folder_order(api_with_namespace):
    api, app = api_with_namespace
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        tag = {"name": "pets", "description": "Pet operations"}
        folder = Folder(col, tag)
        order = folder.order
        assert isinstance(order, list)


def test_folder_as_dict(api_with_namespace):
    api, app = api_with_namespace
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        tag = {"name": "pets", "description": "Pet operations"}
        folder = Folder(col, tag)
        d = folder.as_dict()
        assert d["name"] == "pets"
        assert d["description"] == "Pet operations"
        assert "id" in d
        assert "order" in d
        assert "collectionId" in d


def test_folder_as_dict_none_description_excluded(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        tag = {"name": "pets", "description": None}
        folder = Folder(col, tag)
        d = folder.as_dict()
        assert "description" not in d


# Tests for PostmanCollectionV1

def test_collection_init(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        assert col.api is api
        assert col.swagger is False


def test_collection_init_with_swagger(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api, swagger=True)
        assert col.swagger is True


def test_collection_uuid(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        from uuid import UUID
        assert isinstance(col.uuid, UUID)


def test_collection_id(simple_api):
    api, app = simple_api
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        assert isinstance(col.id, str)
        assert len(col.id) == 36


def test_collection_requests_no_swagger(api_with_namespace):
    api, app = api_with_namespace
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        reqs = list(col.requests)
        assert len(reqs) > 0
        # No swagger spec request
        assert all(r.path != "/swagger.json" for r in reqs)


def test_collection_requests_with_swagger(api_with_namespace):
    api, app = api_with_namespace
    with app.test_request_context():
        col = PostmanCollectionV1(api, swagger=True)
        reqs = list(col.requests)
        assert any(r.path == "/swagger.json" for r in reqs)


def test_collection_requests_all_are_request_objects(api_with_namespace):
    api, app = api_with_namespace
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        for req in col.requests:
            assert isinstance(req, Request)


def test_collection_folders(api_with_namespace):
    api, app = api_with_namespace
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        folders = list(col.folders)
        assert len(folders) == 1
        assert folders[0].tag == "pets"


def test_collection_folders_are_folder_objects(api_with_namespace):
    api, app = api_with_namespace
    with app.test_request_context():
        col = PostmanCollectionV1(api)
        for folder in col.folders:
            assert isinstance(folder, Folder)


def test_collection_apikeys_empty(simple_api):
    api, app = simple_api
    with app.test_request_context():
        schema = api.__schema__
        schema["securityDefinitions"] = {}
        col = PostmanCollectionV1(api)
        assert col.apikeys == {}


def test_collection_apikeys_with_header_apikey(app):
    api = Api(app, title="T", version="1.0")
    with app.test_request_context():
        schema = api.__schema__
        schema["securityDefinitions"] = {
            "apikey": {"in": "header", "name": "X-Api-Key", "type": "apiKey"},
            "oauth2": {"in": "query", "name": "access_token", "type": "oauth2"},
        }
        col = PostmanCollectionV1(api)
        apikeys = col.apikeys
        assert "apikey" in apikeys
        assert apikeys["apikey"] == "X-Api-Key"
        assert "oauth2" not in apikeys


def test_collection_apikeys_only_header_type(app):
    api = Api(app, title="T", version="1.0")
    with app.test_request_context():
        schema = api.__schema__
        schema["securityDefinitions"] = {
            "query_key": {"in": "query", "name": "api_key", "type": "apiKey"},
        }
        col = PostmanCollectionV1(api)
        assert col.apikeys == {}


def test_collection_as_dict(api_with_namespace):
    api, app = api_with_namespace
    with app.test_request_context():
        schema = api.__schema__
        schema["securityDefinitions"] = {}
        col = PostmanCollectionV1(api)
        d = col.as_dict()
        assert d["id"] == col.id
        assert "Test API" in d["name"]
        assert "requests" in d
        assert "folders" in d
        assert "order" in d
        assert "timestamp" in d


def test_collection_as_dict_no_description_excluded(app):
    api = Api(app, title="T", version="1.0")
    with app.test_request_context():
        schema = api.__schema__
        schema["securityDefinitions"] = {}
        col = PostmanCollectionV1(api)
        d = col.as_dict()
        assert "description" not in d


def test_collection_as_dict_with_description(app):
    api = Api(app, title="T", version="1.0", description="My desc")
    with app.test_request_context():
        schema = api.__schema__
        schema["securityDefinitions"] = {}
        col = PostmanCollectionV1(api)
        d = col.as_dict()
        assert d["description"] == "My desc"


def test_collection_as_dict_urlvars(api_with_namespace):
    api, app = api_with_namespace
    with app.test_request_context():
        schema = api.__schema__
        schema["securityDefinitions"] = {}
        col = PostmanCollectionV1(api)
        d = col.as_dict(urlvars=True)
        assert "requests" in d
