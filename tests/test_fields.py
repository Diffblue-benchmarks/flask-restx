"""Unit tests for flask_restx/fields.py"""
import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import flask

from flask_restx import fields
from flask_restx.fields import (
    MarshallingError,
    is_indexable_but_not_string,
    is_integer_indexable,
    get_value,
    _get_value_for_keys,
    _get_value_for_key,
    to_marshallable_type,
    Raw,
    Nested,
    List,
    StringMixin,
    MinMaxMixin,
    NumberMixin,
    String,
    Integer,
    Float,
    Arbitrary,
    Fixed,
    Boolean,
    DateTime,
    Date,
    Url,
    FormattedString,
    ClassName,
    Polymorph,
    Wildcard,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    app = flask.Flask(__name__)
    app.config["TESTING"] = True
    app.config["SERVER_NAME"] = "localhost"
    return app


# ---------------------------------------------------------------------------
# Helper model stubs for Nested / Polymorph tests
# ---------------------------------------------------------------------------

def _make_model(name, fields_dict=None):
    """Create a minimal model stub that satisfies Nested requirements."""
    model = MagicMock()
    model.name = name
    model.resolved = model
    model.ancestors = {name}
    model.get_parent = lambda n: model
    if fields_dict is not None:
        model.__iter__ = lambda self: iter(fields_dict.items())
        model.items = lambda: fields_dict.items()
    return model


# ---------------------------------------------------------------------------
# MarshallingError
# ---------------------------------------------------------------------------

class MarshallingErrorTest:
    def test_init_stores_message(self):
        err = MarshallingError(ValueError("something went wrong"))
        assert str(err) == "something went wrong"

    def test_init_with_string(self):
        err = MarshallingError("plain error")
        assert str(err) == "plain error"


# ---------------------------------------------------------------------------
# is_indexable_but_not_string
# ---------------------------------------------------------------------------

class IsIndexableButNotStringTest:
    def test_list_returns_true(self):
        assert is_indexable_but_not_string([1, 2, 3]) is True

    def test_dict_returns_true(self):
        assert is_indexable_but_not_string({"a": 1}) is True

    def test_string_returns_false(self):
        assert is_indexable_but_not_string("hello") is False

    def test_int_returns_false(self):
        assert is_indexable_but_not_string(42) is False


# ---------------------------------------------------------------------------
# is_integer_indexable
# ---------------------------------------------------------------------------

class IsIntegerIndexableTest:
    def test_list_returns_true(self):
        assert is_integer_indexable([1, 2]) is True

    def test_tuple_returns_true(self):
        assert is_integer_indexable((1, 2)) is True

    def test_dict_returns_false(self):
        assert is_integer_indexable({"a": 1}) is False

    def test_string_returns_false(self):
        assert is_integer_indexable("abc") is False


# ---------------------------------------------------------------------------
# get_value
# ---------------------------------------------------------------------------

class GetValueTest:
    def test_integer_key(self):
        result = get_value(1, [10, 20, 30])
        assert result == 20

    def test_callable_key(self):
        result = get_value(lambda obj: obj["x"] * 2, {"x": 5})
        assert result == 10

    def test_string_key_simple(self):
        result = get_value("name", {"name": "Alice"})
        assert result == "Alice"

    def test_string_key_nested(self):
        class Inner:
            b = 42

        class Outer:
            a = Inner()

        result = get_value("a.b", Outer())
        assert result == 42

    def test_default_returned_when_missing(self):
        result = get_value("missing", {}, default="fallback")
        assert result == "fallback"


# ---------------------------------------------------------------------------
# _get_value_for_keys
# ---------------------------------------------------------------------------

class GetValueForKeysTest:
    def test_single_key(self):
        result = _get_value_for_keys(["name"], {"name": "Bob"}, None)
        assert result == "Bob"

    def test_nested_keys(self):
        class Inner:
            val = 99

        class Outer:
            inner = Inner()

        result = _get_value_for_keys(["inner", "val"], Outer(), None)
        assert result == 99

    def test_missing_returns_default(self):
        result = _get_value_for_keys(["missing"], {}, "default_val")
        assert result == "default_val"


# ---------------------------------------------------------------------------
# _get_value_for_key
# ---------------------------------------------------------------------------

class GetValueForKeyTest:
    def test_dict_key(self):
        assert _get_value_for_key("a", {"a": 1}, None) == 1

    def test_list_int_key(self):
        assert _get_value_for_key(0, [10, 20], None) == 10

    def test_list_string_int_key(self):
        assert _get_value_for_key("1", [10, 20], None) == 20

    def test_attribute_fallback(self):
        class Obj:
            x = 7

        assert _get_value_for_key("x", Obj(), None) == 7

    def test_index_error_falls_through(self):
        result = _get_value_for_key("99", {"a": 1}, "default")
        assert result == "default"

    def test_key_error_falls_through(self):
        result = _get_value_for_key("missing", {"a": 1}, "default")
        assert result == "default"


# ---------------------------------------------------------------------------
# to_marshallable_type
# ---------------------------------------------------------------------------

class ToMarshallableTypeTest:
    def test_none_returns_none(self):
        assert to_marshallable_type(None) is None

    def test_object_with_marshallable(self):
        class Obj:
            def __marshallable__(self):
                return {"key": "value"}

        assert to_marshallable_type(Obj()) == {"key": "value"}

    def test_dict_returned_as_is(self):
        d = {"a": 1}
        assert to_marshallable_type(d) is d

    def test_plain_object_returns_dict(self):
        class Obj:
            def __init__(self):
                self.x = 1
                self.y = 2

        result = to_marshallable_type(Obj())
        assert result == {"x": 1, "y": 2}


# ---------------------------------------------------------------------------
# Raw
# ---------------------------------------------------------------------------

class RawTest:
    def test_init_defaults(self):
        f = Raw()
        assert f.default is None
        assert f.attribute is None
        assert f.title is None
        assert f.description is None
        assert f.required is None
        assert f.readonly is None
        assert f.mask is None
        assert f.nullable is None

    def test_init_with_all_params(self):
        f = Raw(
            default=0,
            attribute="attr",
            title="Title",
            description="Desc",
            required=True,
            readonly=True,
            example="ex",
            mask=None,
            nullable=True,
        )
        assert f.default == 0
        assert f.attribute == "attr"
        assert f.title == "Title"
        assert f.required is True

    def test_format_passthrough(self):
        assert Raw().format("hello") == "hello"

    def test_output_simple(self):
        f = Raw()
        result = f.output("name", {"name": "Alice"})
        assert result == "Alice"

    def test_output_with_default(self):
        f = Raw(default="N/A")
        result = f.output("missing", {})
        assert result == "N/A"

    def test_output_none_no_default(self):
        f = Raw()
        result = f.output("missing", {})
        assert result is None

    def test_output_with_attribute(self):
        f = Raw(attribute="real_name")
        result = f.output("alias", {"real_name": "Bob"})
        assert result == "Bob"

    def test_output_marshalling_error_reraises(self):
        class BadField(Raw):
            def format(self, value):
                raise MarshallingError("bad format")

        f = BadField()
        with pytest.raises(MarshallingError):
            f.output("key", {"key": "val"})

    def test_output_with_mask(self):
        mask = MagicMock()
        mask.apply = lambda data: data.upper()
        f = Raw(mask=mask)
        result = f.output("key", {"key": "hello"})
        assert result == "HELLO"

    def test_v_callable(self):
        f = Raw(default=lambda: 42)
        assert f._v("default") == 42

    def test_v_plain_value(self):
        f = Raw(default="constant")
        assert f._v("default") == "constant"

    def test_schema_cached_property(self):
        f = Raw(title="T")
        schema = f.__schema__
        assert schema["title"] == "T"

    def test_schema(self):
        f = Raw(title="MyTitle", description="Desc", readonly=True)
        s = f.schema()
        assert s["title"] == "MyTitle"
        assert s["description"] == "Desc"
        assert s["readOnly"] is True


# ---------------------------------------------------------------------------
# Nested
# ---------------------------------------------------------------------------

class NestedTest:
    def _model(self, name="TestModel"):
        return _make_model(name)

    def test_init(self):
        m = self._model()
        n = Nested(m)
        assert n.model is m
        assert n.allow_null is False
        assert n.skip_none is False
        assert n.as_list is False

    def test_nested_property(self):
        m = self._model()
        n = Nested(m)
        assert n.nested is m.resolved

    def test_nested_property_no_resolved(self):
        m = MagicMock(spec=[])
        m.name = "M"
        n = Nested.__new__(Nested)
        n.model = m
        assert n.nested is m

    def test_output_allow_null(self):
        m = self._model()
        n = Nested(m, allow_null=True)
        result = n.output("missing", {})
        assert result is None

    def test_output_with_default(self):
        m = self._model()
        n = Nested(m, default={})
        result = n.output("missing", {})
        assert result == {}

    def test_schema_as_list(self):
        m = self._model("M")
        n = Nested(m, as_list=True)
        s = n.schema()
        assert s["type"] == "array"
        assert s["items"]["$ref"] == "#/definitions/M"

    def test_schema_nullable(self):
        m = self._model("M")
        n = Nested(m, nullable=True)
        s = n.schema()
        assert "anyOf" in s

    def test_schema_with_ref(self):
        m = self._model("M")
        n = Nested(m)
        s = n.schema()
        assert "$ref" in s

    def test_clone(self):
        m = self._model("M")
        n = Nested(m)
        cloned = n.clone()
        assert isinstance(cloned, Nested)

    def test_clone_with_mask(self):
        m = self._model("M")
        # model needs .resolved attribute for clone with mask
        m.resolved = m
        n = Nested(m)
        mask = MagicMock()
        mask.apply = lambda r: r
        cloned = n.clone(mask=mask)
        assert isinstance(cloned, Nested)

    def test_schema_allOf_when_existing_properties(self):
        # Lines 287-289: allOf path - triggered when schema already has values
        # (e.g. title is set) and as_list is False
        m = self._model("M")
        n = Nested(m, title="My Title")
        s = n.schema()
        assert "allOf" in s
        assert any(item.get("$ref") == "#/definitions/M" for item in s["allOf"])

    def test_schema_nullable_as_list(self):
        # Line 301: nullable + as_list -> anyOf contains array type with items
        m = self._model("M")
        n = Nested(m, as_list=True, nullable=True)
        s = n.schema()
        assert "anyOf" in s
        array_entry = next(
            (item for item in s["anyOf"] if item.get("type") == "array"), None
        )
        assert array_entry is not None
        assert array_entry["items"]["$ref"] == "#/definitions/M"
        null_entry = next(
            (item for item in s["anyOf"] if item.get("type") == "null"), None
        )
        assert null_entry is not None


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

class ListTest:
    def test_init_with_class(self):
        lst = List(String)
        assert isinstance(lst.container, String)

    def test_init_with_instance(self):
        lst = List(String())
        assert isinstance(lst.container, String)

    def test_init_invalid_class_raises(self):
        with pytest.raises(MarshallingError):
            List(int)

    def test_init_invalid_instance_raises(self):
        with pytest.raises(MarshallingError):
            List(42)

    def test_init_with_min_max_unique(self):
        lst = List(String, min_items=1, max_items=5, unique=True)
        assert lst.min_items == 1
        assert lst.max_items == 5
        assert lst.unique is True

    def test_format_basic(self):
        lst = List(String)
        result = lst.format(["a", "b", "c"])
        assert result == ["a", "b", "c"]

    def test_format_set(self):
        lst = List(String)
        result = lst.format({"x"})
        assert result == ["x"]

    def test_format_none(self):
        lst = List(String)
        assert lst.format(None) == []

    def test_output_list(self):
        lst = List(String)
        result = lst.output("items", {"items": ["a", "b"]})
        assert result == ["a", "b"]

    def test_output_none_returns_default(self):
        lst = List(String, default=[])
        result = lst.output("missing", {})
        assert result == []

    def test_schema(self):
        lst = List(String)
        s = lst.schema()
        assert s["type"] == "array"
        assert "items" in s

    def test_schema_min_max(self):
        lst = List(String, min_items=2, max_items=10)
        s = lst.schema()
        assert s["minItems"] == 2
        assert s["maxItems"] == 10

    def test_clone(self):
        lst = List(String)
        cloned = lst.clone()
        assert isinstance(cloned, List)


# ---------------------------------------------------------------------------
# StringMixin
# ---------------------------------------------------------------------------

class StringMixinTest:
    def test_init(self):
        class TestStr(StringMixin, Raw):
            pass

        f = TestStr(min_length=2, max_length=10, pattern="^[a-z]+$")
        assert f.min_length == 2
        assert f.max_length == 10
        assert f.pattern == "^[a-z]+$"

    def test_schema(self):
        class TestStr(StringMixin, Raw):
            pass

        f = TestStr(min_length=1, max_length=5)
        s = f.schema()
        assert s["minLength"] == 1
        assert s["maxLength"] == 5


# ---------------------------------------------------------------------------
# MinMaxMixin
# ---------------------------------------------------------------------------

class MinMaxMixinTest:
    def test_init(self):
        class TestNum(MinMaxMixin, Raw):
            pass

        f = TestNum(min=0, max=100, exclusiveMin=1, exclusiveMax=99)
        assert f.minimum == 0
        assert f.maximum == 100
        assert f.exclusiveMinimum == 1
        assert f.exclusiveMaximum == 99

    def test_schema(self):
        class TestNum(MinMaxMixin, Raw):
            pass

        f = TestNum(min=0, max=100)
        s = f.schema()
        assert s["minimum"] == 0
        assert s["maximum"] == 100


# ---------------------------------------------------------------------------
# NumberMixin
# ---------------------------------------------------------------------------

class NumberMixinTest:
    def test_init(self):
        class TestNum(NumberMixin, Raw):
            pass

        f = TestNum(multiple=5)
        assert f.multiple == 5

    def test_schema(self):
        class TestNum(NumberMixin, Raw):
            pass

        f = TestNum(multiple=5)
        s = f.schema()
        assert s["multipleOf"] == 5


# ---------------------------------------------------------------------------
# String
# ---------------------------------------------------------------------------

class StringTest:
    def test_init_defaults(self):
        f = String()
        assert f.enum is None
        assert f.discriminator is None
        assert f.required is None

    def test_init_with_discriminator(self):
        f = String(discriminator=True)
        assert f.required is True

    def test_format_string(self):
        assert String().format("hello") == "hello"

    def test_format_int(self):
        assert String().format(42) == "42"

    def test_schema_no_enum(self):
        s = String().schema()
        assert "enum" not in s

    def test_schema_with_enum(self):
        f = String(enum=["a", "b"])
        s = f.schema()
        assert s["enum"] == ["a", "b"]
        assert s["example"] == "a"

    def test_schema_with_enum_and_example(self):
        f = String(enum=["a", "b"], example="b")
        s = f.schema()
        assert s["example"] == "b"


# ---------------------------------------------------------------------------
# Integer
# ---------------------------------------------------------------------------

class IntegerTest:
    def test_format_int(self):
        assert Integer().format(5) == 5

    def test_format_string_number(self):
        assert Integer().format("10") == 10

    def test_format_none_returns_default(self):
        f = Integer(default=0)
        assert f.format(None) == 0

    def test_format_invalid_raises(self):
        with pytest.raises(MarshallingError):
            Integer().format("not_a_number")


# ---------------------------------------------------------------------------
# Float
# ---------------------------------------------------------------------------

class FloatTest:
    def test_format_float(self):
        assert Float().format(3.14) == 3.14

    def test_format_string_number(self):
        assert Float().format("2.5") == 2.5

    def test_format_none_returns_default(self):
        f = Float(default=0.0)
        assert f.format(None) == 0.0

    def test_format_invalid_raises(self):
        with pytest.raises(MarshallingError):
            Float().format("nope")


# ---------------------------------------------------------------------------
# Arbitrary
# ---------------------------------------------------------------------------

class ArbitraryTest:
    def test_format_decimal(self):
        result = Arbitrary().format(Decimal("3.14"))
        assert result == "3.14"

    def test_format_int(self):
        result = Arbitrary().format(5)
        assert result == "5"


# ---------------------------------------------------------------------------
# Fixed
# ---------------------------------------------------------------------------

class FixedTest:
    def test_init_default_decimals(self):
        f = Fixed()
        assert f.precision == Decimal("0.00001")

    def test_init_custom_decimals(self):
        f = Fixed(decimals=2)
        assert f.precision == Decimal("0.01")

    def test_format_valid(self):
        result = Fixed(decimals=2).format("3.14159")
        assert result == "3.14"

    def test_format_invalid_raises(self):
        with pytest.raises(MarshallingError):
            Fixed().format("inf")


# ---------------------------------------------------------------------------
# Boolean
# ---------------------------------------------------------------------------

class BooleanTest:
    def test_format_true(self):
        assert Boolean().format(True) is True

    def test_format_false_string(self):
        assert Boolean().format("false") is False


# ---------------------------------------------------------------------------
# DateTime
# ---------------------------------------------------------------------------

class DateTimeTest:
    def test_init_default_format(self):
        f = DateTime()
        assert f.dt_format == "iso8601"

    def test_init_rfc822(self):
        f = DateTime(dt_format="rfc822")
        assert f.dt_format == "rfc822"

    def test_parse_none(self):
        assert DateTime().parse(None) is None

    def test_parse_datetime(self):
        dt = datetime(2021, 1, 1, 12, 0, 0)
        result = DateTime().parse(dt)
        assert result == dt

    def test_parse_date(self):
        d = date(2021, 6, 15)
        result = DateTime().parse(d)
        assert result == datetime(2021, 6, 15)

    def test_parse_iso8601_string(self):
        result = DateTime().parse("2021-01-01T00:00:00")
        assert isinstance(result, datetime)

    def test_parse_unsupported_raises(self):
        with pytest.raises(ValueError):
            DateTime().parse(12345)

    def test_format_iso8601(self):
        dt = datetime(2021, 1, 1, 0, 0, 0)
        result = DateTime().format(dt)
        assert "2021-01-01" in result

    def test_format_rfc822(self):
        dt = datetime(2021, 1, 1, 0, 0, 0)
        result = DateTime(dt_format="rfc822").format(dt)
        assert isinstance(result, str)

    def test_format_unsupported_format_raises(self):
        f = DateTime()
        f.dt_format = "unknown"
        with pytest.raises(MarshallingError):
            f.format(datetime(2021, 1, 1))

    def test_format_rfc822_method(self):
        dt = datetime(2021, 6, 1, 12, 0, 0)
        result = DateTime().format_rfc822(dt)
        assert isinstance(result, str)
        assert "2021" in result

    def test_format_iso8601_method(self):
        dt = datetime(2021, 6, 1, 12, 0, 0)
        result = DateTime().format_iso8601(dt)
        assert result == "2021-06-01T12:00:00"

    def test_for_schema_with_value(self):
        f = DateTime(default=datetime(2021, 1, 1))
        result = f._for_schema("default")
        assert result is not None

    def test_for_schema_none(self):
        f = DateTime()
        assert f._for_schema("default") is None

    def test_schema(self):
        f = DateTime()
        s = f.schema()
        assert "default" in s


# ---------------------------------------------------------------------------
# Date
# ---------------------------------------------------------------------------

class DateTest:
    def test_init(self):
        f = Date()
        assert f.dt_format == "iso8601"

    def test_parse_none(self):
        assert Date().parse(None) is None

    def test_parse_date(self):
        d = date(2021, 5, 10)
        result = Date().parse(d)
        assert result == d

    def test_parse_datetime(self):
        dt = datetime(2021, 5, 10, 12, 0, 0)
        result = Date().parse(dt)
        assert result == date(2021, 5, 10)

    def test_parse_string(self):
        result = Date().parse("2021-05-10")
        assert isinstance(result, date)

    def test_parse_unsupported_raises(self):
        with pytest.raises(ValueError):
            Date().parse(12345)


# ---------------------------------------------------------------------------
# Url
# ---------------------------------------------------------------------------

class UrlTest:
    def test_init(self):
        f = Url(endpoint="index", absolute=True, scheme="https")
        assert f.endpoint == "index"
        assert f.absolute is True
        assert f.scheme == "https"

    def test_output_basic(self, app):
        @app.route("/items/<int:id>")
        def items(id):
            pass

        f = Url(endpoint="items")
        with app.test_request_context("/"):
            result = f.output("id", {"id": 1})
        assert "/items/1" in result

    def test_output_absolute(self, app):
        @app.route("/things/<int:id>")
        def things(id):
            pass

        f = Url(endpoint="things", absolute=True)
        with app.test_request_context("/"):
            result = f.output("id", {"id": 5})
        assert "localhost" in result

    def test_output_with_scheme(self, app):
        @app.route("/stuff/<int:id>")
        def stuff(id):
            pass

        f = Url(endpoint="stuff", absolute=True, scheme="https")
        with app.test_request_context("/"):
            result = f.output("id", {"id": 3})
        assert result.startswith("https://")

    @pytest.mark.skip(reason="Hard to trigger TypeError from url_for in test environment")
    def test_output_type_error_raises(self, app):
        pass


# ---------------------------------------------------------------------------
# FormattedString
# ---------------------------------------------------------------------------

class FormattedStringTest:
    def test_init(self):
        f = FormattedString("Hello {name}")
        assert f.src_str == "Hello {name}"

    def test_output_basic(self):
        f = FormattedString("Hello {name}")
        result = f.output("greeting", {"name": "World"})
        assert result == "Hello World"

    def test_output_error_raises(self):
        f = FormattedString("{name}")
        with pytest.raises(MarshallingError):
            # Pass something that causes a TypeError (not a dict)
            f.output("key", None)


# ---------------------------------------------------------------------------
# ClassName
# ---------------------------------------------------------------------------

class ClassNameTest:
    def test_init(self):
        f = ClassName()
        assert f.dash is False

    def test_init_dash(self):
        f = ClassName(dash=True)
        assert f.dash is True

    def test_output_class_name(self):
        class MyObject:
            pass

        f = ClassName()
        result = f.output("type", MyObject())
        assert result == "MyObject"

    def test_output_dict_returns_object(self):
        f = ClassName()
        result = f.output("type", {})
        assert result == "object"

    def test_output_dash(self):
        class MyObject:
            pass

        f = ClassName(dash=True)
        result = f.output("type", MyObject())
        assert result == "my_object"


# ---------------------------------------------------------------------------
# Polymorph
# ---------------------------------------------------------------------------

class PolymorphTest:
    def _make_mapping(self):
        parent = _make_model("Parent")
        child1 = _make_model("Child1")
        child2 = _make_model("Child2")
        child1.ancestors = {"Parent", "Child1"}
        child2.ancestors = {"Parent", "Child2"}
        child1.get_parent = lambda n: parent
        child2.get_parent = lambda n: parent
        parent.resolved = parent

        class Child1Class:
            pass

        class Child2Class:
            pass

        return {Child1Class: child1, Child2Class: child2}, Child1Class, child2, parent

    def test_init(self):
        mapping, Child1Class, child2, parent = self._make_mapping()
        p = Polymorph(mapping)
        assert isinstance(p, Polymorph)

    def test_resolve_ancestor(self):
        mapping, Child1Class, child2, parent = self._make_mapping()
        models = list(mapping.values())
        p = Polymorph.__new__(Polymorph)
        result = p.resolve_ancestor(models)
        assert result is not None

    def test_resolve_ancestor_multiple_candidates_raises(self):
        m1 = _make_model("M1")
        m2 = _make_model("M2")
        m1.ancestors = {"A", "B"}
        m2.ancestors = {"A", "B"}
        p = Polymorph.__new__(Polymorph)
        with pytest.raises(ValueError):
            p.resolve_ancestor([m1, m2])

    def test_output_allow_null(self):
        mapping, Child1Class, child2, parent = self._make_mapping()
        p = Polymorph(mapping)
        result = p.output("key", {"key": None})
        assert result is None

    def test_output_unknown_class_raises(self):
        mapping, Child1Class, child2, parent = self._make_mapping()
        p = Polymorph(mapping)

        class Unknown:
            pass

        with pytest.raises(ValueError, match="Unknown class"):
            p.output("key", {"key": Unknown()})

    def test_clone(self):
        mapping, Child1Class, child2, parent = self._make_mapping()
        p = Polymorph(mapping)
        cloned = p.clone()
        assert isinstance(cloned, Polymorph)

    def test_output_returns_default_when_value_none_and_not_allow_null(self):
        # Covers lines 761-762: elif self.default is not None: return self.default
        mapping, Child1Class, child2, parent = self._make_mapping()
        p = Polymorph(mapping, required=True, default="fallback")
        result = p.output("key", {"key": None})
        assert result == "fallback"

    def test_output_raises_for_value_without_class_attr(self):
        # Covers line 766: raise ValueError("Polymorph field only accept class instances")
        mapping, Child1Class, child2, parent = self._make_mapping()
        p = Polymorph(mapping)

        class NoClassAttr:
            def __getattribute__(self, name):
                if name == "__class__":
                    raise AttributeError("no __class__")
                return super().__getattribute__(name)

        with pytest.raises(ValueError, match="Polymorph field only accept class instances"):
            p.output("key", {"key": NoClassAttr()})

    def test_output_raises_for_multiple_candidates(self):
        # Covers lines 774-775: elif len(candidates) > 1: raise ValueError(...)
        mapping, Child1Class, child2, parent = self._make_mapping()
        p = Polymorph(mapping)
        obj = Child1Class()
        mock_mapping = MagicMock()
        mock_mapping.items.return_value = [(Child1Class, child2), (Child1Class, child2)]
        p.mapping = mock_mapping
        with pytest.raises(ValueError, match="Unable to determine"):
            p.output("key", {"key": obj})

    def test_output_marshals_matching_candidate(self):
        # Covers line 779: return marshal(...)
        mapping, Child1Class, child2, parent = self._make_mapping()
        p = Polymorph(mapping)
        obj = Child1Class()
        with patch("flask_restx.fields.marshal") as mock_marshal:
            mock_marshal.return_value = {"field": "value"}
            result = p.output("key", {"key": obj})
        assert result == {"field": "value"}
        mock_marshal.assert_called_once()


# ---------------------------------------------------------------------------
# Wildcard
# ---------------------------------------------------------------------------

class WildcardTest:
    def test_init_with_class(self):
        w = Wildcard(String)
        assert isinstance(w.container, String)

    def test_init_with_instance(self):
        w = Wildcard(String())
        assert isinstance(w.container, String)

    def test_init_invalid_class_raises(self):
        with pytest.raises(MarshallingError):
            Wildcard(int)

    def test_init_invalid_instance_raises(self):
        with pytest.raises(MarshallingError):
            Wildcard(42)

    def test_flatten_none(self):
        w = Wildcard(String)
        assert w._flatten(None) is None

    def test_flatten_dict(self):
        w = Wildcard(String)
        result = w._flatten({"a": 1, "b": 2})
        assert ("a", 1) in result
        assert ("b", 2) in result

    def test_flatten_object(self):
        class Obj:
            x = 1
            y = 2

        w = Wildcard(String)
        result = w._flatten(Obj())
        keys = [k for k, v in result]
        assert "x" in keys
        assert "y" in keys

    def test_flatten_caches_same_obj(self):
        w = Wildcard(String)
        obj = {"a": 1}
        first = w._flatten(obj)
        second = w._flatten(obj)
        assert first is second

    def test_key_property(self):
        w = Wildcard(String)
        w._last = "some_key"
        assert w.key == "some_key"

    def test_reset(self):
        w = Wildcard(String)
        w._last = "key"
        w._flat = [("a", 1)]
        w._cache = {"a"}
        w.exclude = {"b"}
        w.reset()
        assert w._last is None
        assert w._flat is None
        assert w._cache == set()
        assert w.exclude == set()

    def test_output_dict_match(self):
        w = Wildcard(String)
        result = w.output("*", {"hello": "world", "foo": "bar"})
        assert result is not None

    def test_output_no_match_returns_none(self):
        w = Wildcard(String)
        result = w.output("xyz_*", {"abc": "val"})
        assert result is None

    def test_output_no_match_with_default(self):
        w = Wildcard(String, default="fallback")
        result = w.output("xyz_*", {"abc": "val"})
        assert result == "fallback"

    def test_output_ordered(self):
        w = Wildcard(String)
        obj = {"a_val": "1", "b_val": "2"}
        result = w.output("*_val", obj, ordered=True)
        assert result is not None

    def test_schema(self):
        w = Wildcard(String)
        s = w.schema()
        assert s["type"] == "object"
        assert "additionalProperties" in s

    def test_clone(self):
        w = Wildcard(String)
        cloned = w.clone()
        assert isinstance(cloned, Wildcard)
