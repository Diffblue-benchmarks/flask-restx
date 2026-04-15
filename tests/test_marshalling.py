"""Unit tests for flask_restx.marshalling module."""

from collections import OrderedDict

import pytest
import flask
from flask_restx import fields
from flask_restx.marshalling import make, marshal, marshal_with, marshal_with_field


@pytest.fixture
def app():
    app = flask.Flask(__name__)
    app.config["TESTING"] = True
    app.config["RESTX_MASK_HEADER"] = "X-Fields"
    return app


class MakeTest:
    def test_make_with_class_returns_instance(self):
        result = make(fields.Raw)
        assert isinstance(result, fields.Raw)

    def test_make_with_instance_returns_same(self):
        instance = fields.Raw()
        result = make(instance)
        assert result is instance

    def test_make_with_string_class_returns_instance(self):
        result = make(fields.String)
        assert isinstance(result, fields.String)


class MarshalTest:
    def test_basic_marshal(self):
        data = {"a": 100, "b": "foo"}
        mfields = {"a": fields.Raw}
        result = marshal(data, mfields)
        assert result == {"a": 100}

    def test_marshal_with_envelope(self):
        data = {"a": 100}
        mfields = {"a": fields.Raw}
        result = marshal(data, mfields, envelope="data")
        assert result == {"data": {"a": 100}}

    def test_marshal_skip_none(self):
        data = {"a": 100, "b": "foo", "c": None}
        mfields = {"a": fields.Raw, "c": fields.Raw, "d": fields.Raw}
        result = marshal(data, mfields, skip_none=True)
        assert result == {"a": 100}

    def test_marshal_ordered(self):
        data = {"a": 100, "c": None, "d": None}
        mfields = {"a": fields.Raw, "c": fields.Raw, "d": fields.Raw}
        result = marshal(data, mfields, ordered=True)
        assert isinstance(result, OrderedDict)
        assert result == OrderedDict([("a", 100), ("c", None), ("d", None)])

    def test_marshal_ordered_with_envelope(self):
        data = {"a": 100}
        mfields = {"a": fields.Raw}
        result = marshal(data, mfields, envelope="data", ordered=True)
        assert isinstance(result, OrderedDict)
        assert "data" in result
        assert isinstance(result["data"], OrderedDict)

    def test_marshal_skip_none_ordered(self):
        data = {"a": 100, "c": None}
        mfields = {"a": fields.Raw, "c": fields.Raw}
        result = marshal(data, mfields, skip_none=True, ordered=True)
        assert isinstance(result, OrderedDict)
        assert result == OrderedDict([("a", 100)])

    def test_marshal_list_of_dicts(self):
        data = [{"a": 1}, {"a": 2}]
        mfields = {"a": fields.Raw}
        result = marshal(data, mfields)
        assert result == [{"a": 1}, {"a": 2}]

    def test_marshal_tuple_data(self):
        data = ({"a": 1}, {"a": 2})
        mfields = {"a": fields.Raw}
        result = marshal(data, mfields)
        assert result == [{"a": 1}, {"a": 2}]

    def test_marshal_list_with_envelope(self):
        data = [{"a": 1}]
        mfields = {"a": fields.Raw}
        result = marshal(data, mfields, envelope="items")
        assert result == {"items": [{"a": 1}]}

    def test_marshal_nested_dict_field(self):
        data = {"a": 100, "b": "foo"}
        mfields = {"nested": {"a": fields.Raw}}
        result = marshal(data, mfields)
        assert result == {"nested": {"a": 100}}

    def test_marshal_missing_key_returns_none(self):
        data = {"a": 100}
        mfields = {"a": fields.Raw, "d": fields.Raw}
        result = marshal(data, mfields)
        assert result["d"] is None

    def test_marshal_with_wildcard(self):
        data = {"a": 1, "b": 2, "c": 3}
        mfields = OrderedDict([("a", fields.Raw), ("*", fields.Wildcard(fields.Raw))])
        result = marshal(data, mfields)
        assert result.get("a") == 1
        assert result.get("b") == 2
        assert result.get("c") == 3

    def test_marshal_with_wildcard_skip_none(self):
        data = {"a": 1, "b": None, "c": 3}
        mfields = OrderedDict([("*", fields.Wildcard(fields.Raw))])
        result = marshal(data, mfields, skip_none=True)
        assert "b" not in result or result.get("b") is not None


class MarshalWithTest:
    def test_init_stores_fields(self):
        mfields = {"a": fields.Raw}
        decorator = marshal_with(mfields)
        assert decorator.fields is mfields

    def test_init_stores_envelope(self):
        mfields = {"a": fields.Raw}
        decorator = marshal_with(mfields, envelope="data")
        assert decorator.envelope == "data"

    def test_init_stores_skip_none(self):
        mfields = {"a": fields.Raw}
        decorator = marshal_with(mfields, skip_none=True)
        assert decorator.skip_none is True

    def test_init_stores_ordered(self):
        mfields = {"a": fields.Raw}
        decorator = marshal_with(mfields, ordered=True)
        assert decorator.ordered is True

    def test_init_defaults(self):
        mfields = {"a": fields.Raw}
        decorator = marshal_with(mfields)
        assert decorator.envelope is None
        assert decorator.skip_none is False
        assert decorator.ordered is False

    def test_call_decorates_function(self):
        mfields = {"a": fields.Raw}

        @marshal_with(mfields)
        def get():
            return {"a": 100, "b": "foo"}

        result = get()
        assert "a" in result
        assert result["a"] == 100

    def test_call_with_envelope(self):
        mfields = {"a": fields.Raw}

        @marshal_with(mfields, envelope="data")
        def get():
            return {"a": 100}

        result = get()
        assert "data" in result

    def test_call_with_tuple_response(self):
        mfields = {"a": fields.Raw}

        @marshal_with(mfields)
        def get():
            return {"a": 100}, 201

        result = get()
        assert isinstance(result, tuple)
        data, code, headers = result
        assert code == 201
        assert data["a"] == 100

    def test_call_with_tuple_response_with_headers(self):
        mfields = {"a": fields.Raw}

        @marshal_with(mfields)
        def get():
            return {"a": 100}, 200, {"X-Custom": "value"}

        result = get()
        assert isinstance(result, tuple)
        data, code, headers = result
        assert code == 200
        assert headers == {"X-Custom": "value"}

    def test_call_with_app_context(self, app):
        mfields = {"a": fields.Raw}

        @marshal_with(mfields)
        def get():
            return {"a": 100}

        with app.test_request_context("/"):
            result = get()
            assert result["a"] == 100

    def test_call_with_mask_header(self, app):
        mfields = {"a": fields.Raw, "b": fields.Raw}

        @marshal_with(mfields)
        def get():
            return {"a": 100, "b": "foo"}

        with app.test_request_context("/", headers={"X-Fields": "{a}"}):
            result = get()
            assert "a" in result
            assert "b" not in result

    def test_call_ordered(self):
        mfields = {"a": fields.Raw}

        @marshal_with(mfields, ordered=True)
        def get():
            return {"a": 100}

        result = get()
        assert isinstance(result, OrderedDict)

    def test_call_skip_none(self):
        mfields = {"a": fields.Raw, "c": fields.Raw}

        @marshal_with(mfields, skip_none=True)
        def get():
            return {"a": 100, "c": None}

        result = get()
        assert "a" in result
        assert "c" not in result

    def test_wraps_preserves_function_name(self):
        mfields = {"a": fields.Raw}

        @marshal_with(mfields)
        def my_function():
            return {"a": 1}

        assert my_function.__name__ == "my_function"


class MarshalWithFieldTest:
    def test_init_with_class_instantiates(self):
        decorator = marshal_with_field(fields.Integer)
        assert isinstance(decorator.field, fields.Integer)

    def test_init_with_instance_uses_directly(self):
        field_instance = fields.Integer()
        decorator = marshal_with_field(field_instance)
        assert decorator.field is field_instance

    def test_call_formats_return_value(self):
        @marshal_with_field(fields.Integer)
        def get():
            return "42"

        result = get()
        assert result == 42

    def test_call_with_list_field(self):
        @marshal_with_field(fields.List(fields.Integer))
        def get():
            return ["1", 2, 3.0]

        result = get()
        assert result == [1, 2, 3]

    def test_call_with_tuple_response(self):
        @marshal_with_field(fields.Integer)
        def get():
            return "42", 201

        result = get()
        assert isinstance(result, tuple)
        data, code, headers = result
        assert data == 42
        assert code == 201

    def test_call_with_tuple_response_with_headers(self):
        @marshal_with_field(fields.Integer)
        def get():
            return "42", 200, {"X-Custom": "value"}

        result = get()
        data, code, headers = result
        assert data == 42
        assert code == 200
        assert headers == {"X-Custom": "value"}

    def test_wraps_preserves_function_name(self):
        @marshal_with_field(fields.Integer)
        def my_function():
            return "1"

        assert my_function.__name__ == "my_function"
