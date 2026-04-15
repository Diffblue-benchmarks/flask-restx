"""Unit tests for flask_restx.mask module."""
import pytest
from collections import OrderedDict

from flask_restx.mask import Mask, MaskError, ParseError, apply


class MaskInitTest:
    def test_init_no_args(self):
        m = Mask()
        assert m.skip is False
        assert dict(m) == {}

    def test_init_string_mask(self):
        m = Mask("field1,field2")
        assert "field1" in m
        assert "field2" in m

    def test_init_dict_mask(self):
        m = Mask({"a": True, "b": True})
        assert m["a"] is True
        assert m["b"] is True

    def test_init_ordered_dict(self):
        od = OrderedDict([("x", True), ("y", True)])
        m = Mask(od)
        assert list(m.keys()) == ["x", "y"]

    def test_init_skip_true(self):
        m = Mask(skip=True)
        assert m.skip is True

    def test_init_none_mask(self):
        m = Mask(None)
        assert m.skip is False
        assert dict(m) == {}

    def test_init_string_with_skip(self):
        m = Mask("field1", skip=True)
        assert m.skip is True
        assert "field1" in m


class MaskParseTest:
    def test_parse_simple_fields(self):
        m = Mask()
        m.parse("field1,field2,field3")
        assert "field1" in m
        assert "field2" in m
        assert "field3" in m

    def test_parse_with_braces(self):
        m = Mask()
        m.parse("{field1,field2}")
        assert "field1" in m
        assert "field2" in m

    def test_parse_nested(self):
        m = Mask()
        m.parse("field1,nested{sub1,sub2}")
        assert "field1" in m
        assert isinstance(m["nested"], Mask)
        assert "sub1" in m["nested"]
        assert "sub2" in m["nested"]

    def test_parse_empty_string(self):
        m = Mask()
        m.parse("")
        assert dict(m) == {}

    def test_parse_unexpected_opening_bracket(self):
        m = Mask()
        with pytest.raises(ParseError):
            m.parse("{field1,{sub}")

    def test_parse_unexpected_closing_bracket(self):
        m = Mask()
        with pytest.raises(ParseError):
            m.parse("field1}")

    def test_parse_unexpected_comma(self):
        m = Mask()
        with pytest.raises(ParseError):
            m.parse(",field1")

    def test_parse_missing_closing_bracket(self):
        m = Mask()
        with pytest.raises(ParseError):
            m.parse("field1,nested{sub1")

    def test_parse_consecutive_commas(self):
        m = Mask()
        with pytest.raises(ParseError):
            m.parse("field1,,field2")

    def test_parse_wildcard(self):
        m = Mask()
        m.parse("*")
        assert "*" in m

    def test_parse_propagates_skip(self):
        m = Mask(skip=True)
        m.parse("field,nested{sub}")
        assert m["nested"].skip is True


class MaskCleanTest:
    def test_clean_strips_whitespace(self):
        m = Mask()
        result = m.clean("  field  ")
        assert result == "field"

    def test_clean_removes_newlines(self):
        m = Mask()
        result = m.clean("field1\nfield2")
        assert result == "field1field2"

    def test_clean_removes_outer_braces(self):
        m = Mask()
        result = m.clean("{field1,field2}")
        assert result == "field1,field2"

    def test_clean_missing_closing_bracket(self):
        m = Mask()
        with pytest.raises(ParseError):
            m.clean("{field1,field2")

    def test_clean_no_braces(self):
        m = Mask()
        result = m.clean("field1,field2")
        assert result == "field1,field2"


class MaskApplyTest:
    def test_apply_dict(self):
        m = Mask("field1,field2")
        data = {"field1": "a", "field2": "b", "field3": "c"}
        result = m.apply(data)
        assert result == {"field1": "a", "field2": "b"}

    def test_apply_list(self):
        m = Mask("field1")
        data = [{"field1": "a", "field2": "b"}, {"field1": "c", "field2": "d"}]
        result = m.apply(data)
        assert result == [{"field1": "a"}, {"field1": "c"}]

    def test_apply_tuple(self):
        m = Mask("field1")
        data = ({"field1": "a"}, {"field1": "b"})
        result = m.apply(data)
        assert result == [{"field1": "a"}, {"field1": "b"}]

    def test_apply_set(self):
        m = Mask("x")
        data = [{"x": 1}, {"x": 2}]
        result = m.apply(data)
        assert len(result) == 2

    def test_apply_object_with_dict(self):
        class MyObj:
            def __init__(self):
                self.field1 = "val1"
                self.field2 = "val2"

        m = Mask("field1")
        result = m.apply(MyObj())
        assert result == {"field1": "val1"}


class MaskFilterDataTest:
    def test_filter_basic_fields(self):
        m = Mask("a,b")
        data = {"a": 1, "b": 2, "c": 3}
        result = m.filter_data(data)
        assert result == {"a": 1, "b": 2}

    def test_filter_missing_field_no_skip(self):
        m = Mask("a,b")
        data = {"a": 1}
        result = m.filter_data(data)
        assert result == {"a": 1, "b": None}

    def test_filter_missing_field_with_skip(self):
        m = Mask("a,b", skip=True)
        data = {"a": 1}
        result = m.filter_data(data)
        assert result == {"a": 1}

    def test_filter_nested_mask(self):
        m = Mask("a,nested{x,y}")
        data = {"a": 1, "nested": {"x": 10, "y": 20, "z": 30}}
        result = m.filter_data(data)
        assert result == {"a": 1, "nested": {"x": 10, "y": 20}}

    def test_filter_nested_missing_no_skip(self):
        m = Mask("nested{x}")
        data = {}
        result = m.filter_data(data)
        assert result == {"nested": None}

    def test_filter_nested_missing_with_skip(self):
        m = Mask("nested{x}", skip=True)
        data = {}
        result = m.filter_data(data)
        assert result == {}

    def test_filter_wildcard(self):
        m = Mask("a,*")
        data = {"a": 1, "b": 2, "c": 3}
        result = m.filter_data(data)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_filter_wildcard_only(self):
        m = Mask("*")
        data = {"a": 1, "b": 2}
        result = m.filter_data(data)
        assert result == {"a": 1, "b": 2}


class MaskStrTest:
    def test_str_simple(self):
        m = Mask("field1,field2")
        assert str(m) == "{field1,field2}"

    def test_str_nested(self):
        m = Mask("field1,nested{sub1,sub2}")
        s = str(m)
        assert "field1" in s
        assert "nested" in s
        assert "sub1" in s
        assert "sub2" in s

    def test_str_empty(self):
        m = Mask()
        assert str(m) == "{}"

    def test_str_wildcard(self):
        m = Mask("a,*")
        s = str(m)
        assert "*" in s
        assert "a" in s


class ApplyFunctionTest:
    def test_apply_basic(self):
        data = {"field1": "a", "field2": "b", "field3": "c"}
        result = apply(data, "field1,field2")
        assert result == {"field1": "a", "field2": "b"}

    def test_apply_with_mask_object(self):
        data = {"a": 1, "b": 2}
        mask = Mask("a")
        result = apply(data, mask)
        assert result == {"a": 1}

    def test_apply_with_skip(self):
        data = {"a": 1}
        result = apply(data, "a,b", skip=True)
        assert result == {"a": 1}

    def test_apply_skip_false(self):
        data = {"a": 1}
        result = apply(data, "a,b", skip=False)
        assert result == {"a": 1, "b": None}

    def test_apply_list(self):
        data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        result = apply(data, "a")
        assert result == [{"a": 1}, {"a": 3}]

    def test_apply_nested(self):
        data = {"top": {"x": 1, "y": 2}}
        result = apply(data, "top{x}")
        assert result == {"top": {"x": 1}}
