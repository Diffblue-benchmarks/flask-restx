import pytest
import flask
from werkzeug.exceptions import HTTPException

from flask_restx.errors import abort, RestError, ValidationError, SpecsError


@pytest.fixture
def app():
    app = flask.Flask(__name__)
    return app


def test_abort_raises_http_exception(app):
    with app.test_request_context():
        with pytest.raises(HTTPException) as exc_info:
            abort(404)
        assert exc_info.value.code == 404


def test_abort_default_code(app):
    with app.test_request_context():
        with pytest.raises(HTTPException) as exc_info:
            abort()
        assert exc_info.value.code == 500


def test_abort_with_message(app):
    with app.test_request_context():
        with pytest.raises(HTTPException) as exc_info:
            abort(400, message="Bad input")
        assert exc_info.value.data["message"] == "Bad input"


def test_abort_with_kwargs(app):
    with app.test_request_context():
        with pytest.raises(HTTPException) as exc_info:
            abort(400, errors={"field": "required"})
        assert exc_info.value.data["errors"] == {"field": "required"}


def test_abort_with_message_and_kwargs(app):
    with app.test_request_context():
        with pytest.raises(HTTPException) as exc_info:
            abort(422, message="Validation failed", field="name")
        assert exc_info.value.data["message"] == "Validation failed"
        assert exc_info.value.data["field"] == "name"


def test_abort_no_data_when_no_message_no_kwargs(app):
    with app.test_request_context():
        with pytest.raises(HTTPException) as exc_info:
            abort(404)
        assert not hasattr(exc_info.value, "data") or exc_info.value.data is None or "message" not in getattr(exc_info.value, "data", {})


def test_rest_error_init_stores_message():
    error = RestError("something went wrong")
    assert error.msg == "something went wrong"


def test_rest_error_str_returns_message():
    error = RestError("something went wrong")
    assert str(error) == "something went wrong"


def test_rest_error_is_exception():
    error = RestError("test")
    assert isinstance(error, Exception)


def test_validation_error():
    error = ValidationError("invalid value")
    assert isinstance(error, RestError)
    assert str(error) == "invalid value"


def test_specs_error():
    error = SpecsError("bad spec")
    assert isinstance(error, RestError)
    assert str(error) == "bad spec"
