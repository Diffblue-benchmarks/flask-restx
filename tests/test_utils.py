import pytest
import warnings
from collections import OrderedDict

from flask_restx.utils import (
    import_werkzeug_response,
    merge,
    camel_to_dash,
    default_id,
    not_none,
    not_none_sorted,
    unpack,
    to_view_name,
    import_check_view_func,
    FlaskCompatibilityWarning,
)
from flask_restx._http import HTTPStatus


class ImportWerkzeugResponseTest:
    def test_returns_a_class(self):
        result = import_werkzeug_response()
        assert result is not None
        assert isinstance(result, type)

    def test_returns_werkzeug_response_class(self):
        result = import_werkzeug_response()
        assert result.__name__ in ("Response", "BaseResponse")


class MergeTest:
    def test_merge_simple_dicts(self):
        first = {"a": 1}
        second = {"b": 2}
        result = merge(first, second)
        assert result == {"a": 1, "b": 2}

    def test_second_overrides_first(self):
        first = {"a": 1}
        second = {"a": 2}
        result = merge(first, second)
        assert result == {"a": 2}

    def test_nested_dicts_are_merged(self):
        first = {"a": {"x": 1, "y": 2}}
        second = {"a": {"y": 3, "z": 4}}
        result = merge(first, second)
        assert result == {"a": {"x": 1, "y": 3, "z": 4}}

    def test_non_dict_second_returns_second(self):
        result = merge({"a": 1}, "string")
        assert result == "string"

    def test_does_not_modify_originals(self):
        first = {"a": {"x": 1}}
        second = {"a": {"y": 2}}
        merge(first, second)
        assert first == {"a": {"x": 1}}
        assert second == {"a": {"y": 2}}

    def test_merge_empty_dicts(self):
        assert merge({}, {}) == {}

    def test_merge_first_empty(self):
        assert merge({}, {"a": 1}) == {"a": 1}

    def test_merge_second_empty(self):
        assert merge({"a": 1}, {}) == {"a": 1}


class CamelToDashTest:
    def test_simple_camel_case(self):
        assert camel_to_dash("CamelCase") == "camel_case"

    def test_all_lowercase(self):
        assert camel_to_dash("lowercase") == "lowercase"

    def test_multiple_words(self):
        assert camel_to_dash("CamelCaseString") == "camel_case_string"

    def test_single_word(self):
        assert camel_to_dash("Word") == "word"

    def test_acronym_handling(self):
        assert camel_to_dash("HTMLParser") == "html_parser"


class DefaultIdTest:
    def test_simple_resource(self):
        result = default_id("MyResource", "get")
        assert result == "get_my_resource"

    def test_lowercase_resource(self):
        result = default_id("resource", "post")
        assert result == "post_resource"

    def test_camel_case_resource(self):
        result = default_id("UserList", "delete")
        assert result == "delete_user_list"


class NotNoneTest:
    def test_removes_none_values(self):
        data = {"a": 1, "b": None, "c": 3}
        assert not_none(data) == {"a": 1, "c": 3}

    def test_empty_dict(self):
        assert not_none({}) == {}

    def test_all_none(self):
        assert not_none({"a": None, "b": None}) == {}

    def test_no_none(self):
        assert not_none({"a": 1, "b": 2}) == {"a": 1, "b": 2}

    def test_zero_and_false_kept(self):
        data = {"a": 0, "b": False, "c": None}
        result = not_none(data)
        assert result == {"a": 0, "b": False}


class NotNoneSortedTest:
    def test_removes_none_and_sorts(self):
        data = OrderedDict([("b", 2), ("a", 1), ("c", None)])
        result = not_none_sorted(data)
        assert list(result.keys()) == ["a", "b"]
        assert result["a"] == 1
        assert result["b"] == 2

    def test_empty_dict(self):
        assert not_none_sorted(OrderedDict()) == OrderedDict()

    def test_all_none(self):
        data = OrderedDict([("a", None), ("b", None)])
        assert not_none_sorted(data) == OrderedDict()

    def test_returns_ordered_dict(self):
        data = {"z": 1, "a": 2}
        result = not_none_sorted(data)
        assert isinstance(result, OrderedDict)
        assert list(result.keys()) == ["a", "z"]


class UnpackTest:
    def test_single_value(self):
        data, code, headers = unpack("response")
        assert data == "response"
        assert code == HTTPStatus.OK
        assert headers == {}

    def test_single_value_tuple(self):
        data, code, headers = unpack(("response",))
        assert data == "response"
        assert code == HTTPStatus.OK
        assert headers == {}

    def test_data_and_code(self):
        data, code, headers = unpack(("response", 201))
        assert data == "response"
        assert code == 201
        assert headers == {}

    def test_data_code_and_headers(self):
        data, code, headers = unpack(("response", 201, {"X-Header": "value"}))
        assert data == "response"
        assert code == 201
        assert headers == {"X-Header": "value"}

    def test_data_code_none_uses_default(self):
        data, code, headers = unpack(("response", None, {}))
        assert code == HTTPStatus.OK

    def test_too_many_values_raises(self):
        with pytest.raises(ValueError):
            unpack(("a", "b", "c", "d"))

    def test_custom_default_code(self):
        data, code, headers = unpack("response", default_code=204)
        assert code == 204


class ToViewNameTest:
    def test_returns_function_name(self):
        def my_view():
            pass

        assert to_view_name(my_view) == "my_view"

    def test_lambda_name(self):
        f = lambda: None
        assert to_view_name(f) == "<lambda>"

    def test_none_raises(self):
        with pytest.raises(AssertionError):
            to_view_name(None)


class ImportCheckViewFuncTest:
    def test_returns_callable(self):
        result = import_check_view_func()
        assert callable(result)

    def test_result_works_as_view_name_func(self):
        func = import_check_view_func()

        def my_endpoint():
            pass

        assert func(my_endpoint) == "my_endpoint"

    def test_import_check_unknown_flask_version(self, mocker):
        mocker.patch("importlib.metadata.version", return_value="99.0.0")
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = import_check_view_func()
        assert callable(result)
