"""Unit tests for flask_restx.schemas module."""

import pytest
from flask_restx import errors
from flask_restx.schemas import (
    SchemaValidationError,
    LazySchema,
    OAS_20,
    VERSIONS,
    validate,
)


class SchemaValidationErrorTest:
    def test_init_stores_msg_and_errors(self):
        err = SchemaValidationError("test msg", errors=[])
        assert err.msg == "test msg"
        assert err.errors == []

    def test_init_errors_none_by_default(self):
        err = SchemaValidationError("msg", errors=None)
        assert err.msg == "msg"
        assert err.errors is None

    def test_str_no_errors(self):
        err = SchemaValidationError("base message", errors=[])
        assert str(err) == "base message"

    def test_str_with_errors(self):
        from jsonschema import ValidationError as JSValidationError
        from collections import deque

        je = JSValidationError("field is required")
        je.path = deque(["info", "title"])
        je.context = []
        err = SchemaValidationError("Validation failed", errors=[je])
        result = str(err)
        assert "Validation failed" in result
        assert "info.title" in result
        assert "field is required" in result

    def test_str_with_suberrors(self):
        from jsonschema import ValidationError as JSValidationError
        from collections import deque

        suberr = JSValidationError("suberror message")
        suberr.schema_path = deque(["properties", "title"])
        suberr.context = []

        je = JSValidationError("parent error")
        je.path = deque(["info"])
        je.context = [suberr]

        err = SchemaValidationError("Top error", errors=[je])
        result = str(err)
        assert "suberror message" in result
        assert "properties.title" in result

    def test_unicode_is_str(self):
        err = SchemaValidationError("msg", errors=[])
        assert err.__unicode__() == str(err)

    def test_is_validation_error(self):
        err = SchemaValidationError("msg", errors=[])
        assert isinstance(err, errors.ValidationError)


class LazySchemaTest:
    def test_init_stores_filename(self):
        schema = LazySchema("oas-2.0.json")
        assert schema.filename == "oas-2.0.json"

    def test_init_schema_none(self):
        schema = LazySchema("oas-2.0.json")
        assert schema._schema is None

    def test_init_custom_validator(self):
        from jsonschema import Draft4Validator

        class FakeValidator:
            pass

        schema = LazySchema("oas-2.0.json", validator=FakeValidator)
        assert schema._validator is FakeValidator

    def test_getitem_loads_schema(self):
        schema = LazySchema("oas-2.0.json")
        value = schema["title"]
        assert value is not None

    def test_iter_loads_schema(self):
        schema = LazySchema("oas-2.0.json")
        keys = list(schema)
        assert len(keys) > 0

    def test_len_loads_schema(self):
        schema = LazySchema("oas-2.0.json")
        assert len(schema) > 0

    def test_load_called_once(self):
        schema = LazySchema("oas-2.0.json")
        _ = schema["title"]
        cached = schema._schema
        _ = schema["title"]
        assert schema._schema is cached

    def test_validator_property(self):
        schema = LazySchema("oas-2.0.json")
        v = schema.validator
        assert v is not None


class ValidateTest:
    def _minimal_valid_spec(self):
        return {
            "swagger": "2.0",
            "info": {
                "title": "Test API",
                "version": "1.0",
            },
            "paths": {},
        }

    def test_valid_spec_returns_true(self):
        assert validate(self._minimal_valid_spec()) is True

    def test_missing_swagger_raises_specs_error(self):
        with pytest.raises(errors.SpecsError) as exc_info:
            validate({})
        assert "Unable to determinate" in str(exc_info.value)

    def test_unknown_version_raises_specs_error(self):
        with pytest.raises(errors.SpecsError) as exc_info:
            validate({"swagger": "99.0"})
        assert "Unknown OpenAPI schema version" in str(exc_info.value)

    def test_invalid_spec_raises_schema_validation_error(self):
        data = {"swagger": "2.0"}  # missing required fields
        with pytest.raises(SchemaValidationError) as exc_info:
            validate(data)
        assert "validation failed" in str(exc_info.value).lower()

    def test_schema_validation_error_has_errors(self):
        data = {"swagger": "2.0"}
        with pytest.raises(SchemaValidationError) as exc_info:
            validate(data)
        assert exc_info.value.errors is not None
        assert len(exc_info.value.errors) > 0
