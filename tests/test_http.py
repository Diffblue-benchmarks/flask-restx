# encoding: utf-8
import pytest
from flask_restx._http import HTTPStatus


def test_http_status_new_value():
    assert HTTPStatus.OK == 200


def test_http_status_new_phrase():
    assert HTTPStatus.OK.phrase == "OK"


def test_http_status_new_description():
    assert HTTPStatus.OK.description == "Request fulfilled, document follows"


def test_http_status_new_default_description():
    assert HTTPStatus.PROCESSING.description == ""


def test_http_status_str():
    assert str(HTTPStatus.OK) == "200"


def test_http_status_str_not_found():
    assert str(HTTPStatus.NOT_FOUND) == "404"
