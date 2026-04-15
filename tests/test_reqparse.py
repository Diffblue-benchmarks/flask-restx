import pytest
from unittest.mock import MagicMock, patch
from werkzeug.datastructures import MultiDict, FileStorage
from werkzeug.exceptions import BadRequest

import flask
from flask import Flask

from flask_restx.reqparse import (
    ParseResult,
    Argument,
    RequestParser,
    _handle_arg_type,
    LOCATIONS,
    PY_TYPES,
)


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["BUNDLE_ERRORS"] = False
    return app


@pytest.fixture
def app_context(app):
    with app.app_context():
        yield app


@pytest.fixture
def request_context(app):
    with app.test_request_context("/"):
        yield app


# ParseResult tests

def test_parse_result_getattr_existing_key():
    result = ParseResult()
    result["foo"] = "bar"
    assert result.foo == "bar"


def test_parse_result_getattr_missing_key():
    result = ParseResult()
    with pytest.raises(AttributeError):
        _ = result.nonexistent


def test_parse_result_setattr():
    result = ParseResult()
    result.foo = "bar"
    assert result["foo"] == "bar"


# Argument.__init__ tests

def test_argument_init_defaults():
    arg = Argument("test_arg")
    assert arg.name == "test_arg"
    assert arg.default is None
    assert arg.dest is None
    assert arg.required is False
    assert arg.ignore is False
    assert arg.location == ("json", "values")
    assert arg.type is str
    assert arg.choices == ()
    assert arg.action == "store"
    assert arg.help is None
    assert arg.case_sensitive is True
    assert arg.operators == ("=",)
    assert arg.store_missing is True
    assert arg.trim is False
    assert arg.nullable is True


def test_argument_init_custom():
    arg = Argument(
        "foo",
        default=42,
        dest="bar",
        required=True,
        ignore=True,
        type=int,
        location="args",
        choices=[1, 2, 3],
        action="append",
        help="help text",
        operators=("=", "!="),
        case_sensitive=False,
        store_missing=False,
        trim=True,
        nullable=False,
    )
    assert arg.name == "foo"
    assert arg.default == 42
    assert arg.dest == "bar"
    assert arg.required is True
    assert arg.ignore is True
    assert arg.type is int
    assert arg.location == "args"
    assert arg.choices == [1, 2, 3]
    assert arg.action == "append"
    assert arg.help == "help text"
    assert arg.operators == ("=", "!=")
    assert arg.case_sensitive is False
    assert arg.store_missing is False
    assert arg.trim is True
    assert arg.nullable is False


# Argument.source tests

def test_argument_source_string_location_json(request_context):
    arg = Argument("data", location="json")
    mock_request = MagicMock()
    mock_request.get_json.return_value = {"key": "value"}
    result = arg.source(mock_request)
    assert result == {"key": "value"}


def test_argument_source_string_location_get_json(request_context):
    arg = Argument("data", location="get_json")
    mock_request = MagicMock()
    mock_request.get_json.return_value = {"key": "value"}
    result = arg.source(mock_request)
    assert result == {"key": "value"}


def test_argument_source_string_location_args(request_context):
    arg = Argument("data", location="args")
    mock_request = MagicMock()
    mock_request.args = MultiDict([("foo", "bar")])
    result = arg.source(mock_request)
    assert result == MultiDict([("foo", "bar")])


def test_argument_source_string_location_callable(request_context):
    arg = Argument("data", location="args")
    mock_request = MagicMock()
    md = MultiDict([("foo", "bar")])
    mock_request.args = lambda: md
    result = arg.source(mock_request)
    assert result == md


def test_argument_source_string_location_none_returns_multidict(request_context):
    arg = Argument("data", location="args")
    mock_request = MagicMock()
    mock_request.args = None
    result = arg.source(mock_request)
    assert isinstance(result, MultiDict)


def test_argument_source_iterable_location(request_context):
    arg = Argument("data", location=("json", "values"))
    mock_request = MagicMock()
    mock_request.get_json.return_value = {"key": "value"}
    mock_request.values = MultiDict([("other", "val")])
    result = arg.source(mock_request)
    assert "key" in result
    assert "other" in result


def test_argument_source_iterable_location_none_value(request_context):
    arg = Argument("data", location=("json", "values"))
    mock_request = MagicMock()
    mock_request.get_json.return_value = None
    mock_request.values = None
    result = arg.source(mock_request)
    assert isinstance(result, MultiDict)


# Argument.convert tests

def test_argument_convert_none_nullable():
    arg = Argument("test", nullable=True)
    assert arg.convert(None, "=") is None


def test_argument_convert_none_not_nullable():
    arg = Argument("test", nullable=False)
    with pytest.raises(ValueError, match="Must not be null!"):
        arg.convert(None, "=")


def test_argument_convert_string():
    arg = Argument("test", type=str)
    assert arg.convert("hello", "=") == "hello"


def test_argument_convert_int():
    arg = Argument("test", type=int)
    assert arg.convert("42", "=") == 42


def test_argument_convert_file_storage():
    arg = Argument("file", type=FileStorage)
    fs = MagicMock(spec=FileStorage)
    result = arg.convert(fs, "=")
    assert result is fs


def test_argument_convert_with_type_error_fallback():
    def my_type(val):
        return int(val)

    arg = Argument("test", type=my_type)
    assert arg.convert("5", "=") == 5


# Argument.handle_validation_error tests

def test_argument_handle_validation_error_bundle(app_context):
    arg = Argument("test")
    error = ValueError("bad value")
    result, errors = arg.handle_validation_error(error, bundle_errors=True)
    assert isinstance(result, ValueError)
    assert errors == {"test": "bad value"}


def test_argument_handle_validation_error_with_help_bundle(app_context):
    arg = Argument("test", help="This field")
    error = ValueError("is invalid")
    result, errors = arg.handle_validation_error(error, bundle_errors=True)
    assert "This field" in errors["test"]
    assert "is invalid" in errors["test"]


def test_argument_handle_validation_error_abort(app_context):
    arg = Argument("test")
    error = ValueError("bad value")
    with pytest.raises(Exception):
        arg.handle_validation_error(error, bundle_errors=False)


# Argument.parse tests

def test_argument_parse_simple(app_context):
    arg = Argument("foo", location="args")
    mock_request = MagicMock()
    mock_request.args = MultiDict([("foo", "bar")])
    mock_request.unparsed_arguments = {}
    value, found = arg.parse(mock_request)
    assert value == "bar"
    assert found is True


def test_argument_parse_missing_not_required(app_context):
    arg = Argument("foo", location="args", default="default_val")
    mock_request = MagicMock()
    mock_request.args = MultiDict()
    mock_request.unparsed_arguments = {}
    value, found = arg.parse(mock_request)
    assert value == "default_val"
    assert found is False


def test_argument_parse_required_missing(app_context):
    arg = Argument("foo", location="args", required=True)
    mock_request = MagicMock()
    mock_request.args = MultiDict()
    mock_request.unparsed_arguments = {}
    with pytest.raises(Exception):
        arg.parse(mock_request)


def test_argument_parse_required_missing_bundle(app_context):
    arg = Argument("foo", location="args", required=True)
    mock_request = MagicMock()
    mock_request.args = MultiDict()
    mock_request.unparsed_arguments = {}
    result, errors = arg.parse(mock_request, bundle_errors=True)
    assert isinstance(result, ValueError)
    assert "foo" in errors


def test_argument_parse_trim(app_context):
    arg = Argument("foo", location="args", trim=True)
    mock_request = MagicMock()
    mock_request.args = MultiDict([("foo", "  bar  ")])
    mock_request.unparsed_arguments = {}
    value, found = arg.parse(mock_request)
    assert value == "bar"


def test_argument_parse_case_insensitive(app_context):
    arg = Argument("foo", location="args", case_sensitive=False)
    mock_request = MagicMock()
    mock_request.args = MultiDict([("foo", "BAR")])
    mock_request.unparsed_arguments = {}
    value, found = arg.parse(mock_request)
    assert value == "bar"


def test_argument_parse_action_append(app_context):
    arg = Argument("foo", location="args", action="append")
    mock_request = MagicMock()
    mock_request.args = MultiDict([("foo", "a"), ("foo", "b")])
    mock_request.unparsed_arguments = {}
    value, found = arg.parse(mock_request)
    assert value == ["a", "b"]
    assert found is True


def test_argument_parse_action_split(app_context):
    arg = Argument("foo", location="args", action="split")
    mock_request = MagicMock()
    mock_request.args = MultiDict([("foo", "a,b,c")])
    mock_request.unparsed_arguments = {}
    value, found = arg.parse(mock_request)
    assert value == ["a", "b", "c"]


def test_argument_parse_invalid_choice(app_context):
    arg = Argument("foo", location="args", choices=["a", "b"])
    mock_request = MagicMock()
    mock_request.args = MultiDict([("foo", "c")])
    mock_request.unparsed_arguments = {}
    with pytest.raises(Exception):
        arg.parse(mock_request)


def test_argument_parse_invalid_choice_bundle(app_context):
    arg = Argument("foo", location="args", choices=["a", "b"])
    mock_request = MagicMock()
    mock_request.args = MultiDict([("foo", "c")])
    mock_request.unparsed_arguments = {}
    result, errors = arg.parse(mock_request, bundle_errors=True)
    assert isinstance(result, ValueError)


def test_argument_parse_callable_default(app_context):
    arg = Argument("foo", location="args", default=lambda: "dynamic")
    mock_request = MagicMock()
    mock_request.args = MultiDict()
    mock_request.unparsed_arguments = {}
    value, found = arg.parse(mock_request)
    assert value == "dynamic"
    assert found is False


def test_argument_parse_ignore_conversion_error(app_context):
    arg = Argument("foo", location="args", type=int, ignore=True)
    mock_request = MagicMock()
    mock_request.args = MultiDict([("foo", "not_int")])
    mock_request.unparsed_arguments = {}
    value, found = arg.parse(mock_request)
    assert value is None
    assert found is False


def test_argument_parse_required_iterable_location_message(app_context):
    arg = Argument("foo", location=("json", "values"), required=True)
    mock_request = MagicMock()
    mock_request.get_json.return_value = None
    mock_request.values = MultiDict()
    mock_request.unparsed_arguments = {}
    result, errors = arg.parse(mock_request, bundle_errors=True)
    assert isinstance(result, ValueError)
    assert "foo" in errors


def test_argument_parse_regular_dict_source(app_context):
    arg = Argument("foo", location="json")
    mock_request = MagicMock()
    mock_request.get_json.return_value = {"foo": "bar"}
    mock_request.unparsed_arguments = {}
    value, found = arg.parse(mock_request)
    assert value == "bar"


# Argument.__schema__ tests

def test_argument_schema_basic():
    arg = Argument("foo", location="args")
    schema = arg.__schema__
    assert schema["name"] == "foo"
    assert schema["in"] == "query"


def test_argument_schema_cookie_returns_none():
    arg = Argument("foo", location="cookie")
    assert arg.__schema__ is None


def test_argument_schema_required():
    arg = Argument("foo", location="args", required=True)
    schema = arg.__schema__
    assert schema["required"] is True


def test_argument_schema_help():
    arg = Argument("foo", location="args", help="A description")
    schema = arg.__schema__
    assert schema["description"] == "A description"


def test_argument_schema_default():
    arg = Argument("foo", location="args", default="default_val")
    schema = arg.__schema__
    assert schema["default"] == "default_val"


def test_argument_schema_callable_default():
    arg = Argument("foo", location="args", default=lambda: "computed")
    schema = arg.__schema__
    assert schema["default"] == "computed"


def test_argument_schema_action_append():
    arg = Argument("foo", location="args", action="append", type=str)
    schema = arg.__schema__
    assert schema["type"] == "array"
    assert schema["collectionFormat"] == "multi"


def test_argument_schema_action_split():
    arg = Argument("foo", location="args", action="split", type=str)
    schema = arg.__schema__
    assert schema["type"] == "array"
    assert schema["collectionFormat"] == "csv"


def test_argument_schema_choices():
    arg = Argument("foo", location="args", choices=["a", "b"])
    schema = arg.__schema__
    assert schema["enum"] == ["a", "b"]


def test_argument_schema_int_type():
    arg = Argument("foo", location="args", type=int)
    schema = arg.__schema__
    assert schema["type"] == "integer"


def test_argument_schema_bool_type():
    arg = Argument("foo", location="args", type=bool)
    schema = arg.__schema__
    assert schema["type"] == "boolean"


def test_argument_schema_none_type():
    arg = Argument("foo", location="args", type=None)
    schema = arg.__schema__
    assert schema["type"] == "void"


# RequestParser.__init__ tests

def test_request_parser_init_defaults():
    parser = RequestParser()
    assert parser.args == []
    assert parser.argument_class is Argument
    assert parser.result_class is ParseResult
    assert parser.trim is False
    assert parser.bundle_errors is False


def test_request_parser_init_custom():
    parser = RequestParser(trim=True, bundle_errors=True)
    assert parser.trim is True
    assert parser.bundle_errors is True


# RequestParser.add_argument tests

def test_request_parser_add_argument_by_name():
    parser = RequestParser()
    result = parser.add_argument("foo")
    assert len(parser.args) == 1
    assert parser.args[0].name == "foo"
    assert result is parser


def test_request_parser_add_argument_instance():
    parser = RequestParser()
    arg = Argument("bar")
    result = parser.add_argument(arg)
    assert len(parser.args) == 1
    assert parser.args[0] is arg
    assert result is parser


def test_request_parser_add_argument_with_trim():
    parser = RequestParser(trim=True)
    parser.add_argument("foo")
    assert parser.args[0].trim is True


def test_request_parser_add_argument_trim_kwarg_override():
    parser = RequestParser(trim=True)
    parser.add_argument("foo", trim=False)
    assert parser.args[0].trim is False


# RequestParser.parse_args tests

def test_request_parser_parse_args_basic(app_context):
    parser = RequestParser()
    parser.add_argument("foo", location="args")
    mock_request = MagicMock()
    mock_request.args = MultiDict([("foo", "bar")])
    mock_request.values = MultiDict()
    mock_request.get_json.return_value = None
    result = parser.parse_args(mock_request)
    assert result.foo == "bar"


def test_request_parser_parse_args_strict_unknown_args(app_context):
    parser = RequestParser()
    parser.add_argument("foo", location="args")
    mock_request = MagicMock()
    mock_request.args = MultiDict([("foo", "bar"), ("unknown", "baz")])
    mock_request.values = MultiDict([("foo", "bar"), ("unknown", "baz")])
    mock_request.get_json.return_value = None
    with pytest.raises(BadRequest):
        parser.parse_args(mock_request, strict=True)


def test_request_parser_parse_args_bundle_errors(app_context):
    parser = RequestParser(bundle_errors=True)
    parser.add_argument("foo", location="args", required=True)
    parser.add_argument("bar", location="args", required=True)
    mock_request = MagicMock()
    mock_request.args = MultiDict()
    mock_request.values = MultiDict()
    mock_request.get_json.return_value = None
    mock_request.unparsed_arguments = {}
    with pytest.raises(Exception):
        parser.parse_args(mock_request)


def test_request_parser_parse_args_store_missing_false(app_context):
    parser = RequestParser()
    parser.add_argument("foo", location="args", store_missing=False)
    mock_request = MagicMock()
    mock_request.args = MultiDict()
    mock_request.values = MultiDict()
    mock_request.get_json.return_value = None
    mock_request.unparsed_arguments = {}
    result = parser.parse_args(mock_request)
    assert "foo" not in result


# RequestParser.copy tests

def test_request_parser_copy():
    parser = RequestParser(trim=True, bundle_errors=True)
    parser.add_argument("foo", location="args")
    parser_copy = parser.copy()
    assert parser_copy is not parser
    assert parser_copy.trim is True
    assert parser_copy.bundle_errors is True
    assert len(parser_copy.args) == 1
    assert parser_copy.args[0].name == "foo"
    assert parser_copy.args[0] is not parser.args[0]


# RequestParser.replace_argument tests

def test_request_parser_replace_argument():
    parser = RequestParser()
    parser.add_argument("foo", type=str)
    parser.replace_argument("foo", type=int)
    assert len(parser.args) == 1
    assert parser.args[0].type is int


def test_request_parser_replace_argument_not_found():
    parser = RequestParser()
    parser.add_argument("foo")
    result = parser.replace_argument("bar")
    assert len(parser.args) == 1
    assert result is parser


# RequestParser.remove_argument tests

def test_request_parser_remove_argument():
    parser = RequestParser()
    parser.add_argument("foo")
    parser.add_argument("bar")
    result = parser.remove_argument("foo")
    assert len(parser.args) == 1
    assert parser.args[0].name == "bar"
    assert result is parser


def test_request_parser_remove_argument_not_found():
    parser = RequestParser()
    parser.add_argument("foo")
    result = parser.remove_argument("bar")
    assert len(parser.args) == 1
    assert result is parser


# RequestParser.__schema__ tests

def test_request_parser_schema_basic():
    parser = RequestParser()
    parser.add_argument("foo", location="args", type=str)
    schema = parser.__schema__
    assert len(schema) == 1
    assert schema[0]["name"] == "foo"


def test_request_parser_schema_body_and_formdata_raises():
    from flask_restx.errors import SpecsError
    parser = RequestParser()
    parser.add_argument("foo", location="json", type=str)
    parser.add_argument("bar", location="form", type=str)
    with pytest.raises(SpecsError):
        _ = parser.__schema__


def test_request_parser_schema_cookie_skipped():
    parser = RequestParser()
    parser.add_argument("foo", location="cookie")
    parser.add_argument("bar", location="args")
    schema = parser.__schema__
    assert len(schema) == 1
    assert schema[0]["name"] == "bar"


# _handle_arg_type tests

def test_handle_arg_type_int():
    arg = Argument("foo", type=int)
    param = {}
    _handle_arg_type(arg, param)
    assert param["type"] == "integer"


def test_handle_arg_type_str():
    arg = Argument("foo", type=str)
    param = {}
    _handle_arg_type(arg, param)
    assert param["type"] == "string"


def test_handle_arg_type_bool():
    arg = Argument("foo", type=bool)
    param = {}
    _handle_arg_type(arg, param)
    assert param["type"] == "boolean"


def test_handle_arg_type_float():
    arg = Argument("foo", type=float)
    param = {}
    _handle_arg_type(arg, param)
    assert param["type"] == "number"


def test_handle_arg_type_none():
    arg = Argument("foo", type=None)
    param = {}
    _handle_arg_type(arg, param)
    assert param["type"] == "void"


def test_handle_arg_type_with_apidoc():
    arg = Argument("foo")
    arg.type = MagicMock()
    arg.type.__apidoc__ = {"name": "MyModel"}
    param = {}
    _handle_arg_type(arg, param)
    assert param["type"] == "MyModel"
    assert param["in"] == "body"


def test_handle_arg_type_with_schema():
    arg = Argument("foo")
    arg.type = MagicMock(spec=["__schema__"])
    del arg.type.__apidoc__
    arg.type.__schema__ = {"type": "object", "properties": {}}
    param = {}
    _handle_arg_type(arg, param)
    assert param["type"] == "object"


def test_handle_arg_type_files():
    arg = Argument("foo", location="files")
    # Use a type not in PY_TYPES and without __apidoc__/__schema__ to reach the files branch
    class CustomType:
        pass
    arg.type = CustomType
    param = {}
    _handle_arg_type(arg, param)
    assert param["type"] == "file"


def test_handle_arg_type_unknown():
    arg = Argument("foo")
    arg.type = lambda x: x  # not in PY_TYPES, no __apidoc__ or __schema__
    param = {}
    _handle_arg_type(arg, param)
    assert param["type"] == "string"
