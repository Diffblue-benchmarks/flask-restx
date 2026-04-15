"""
Unit tests for flask_restx/inputs.py
"""
import copy
import socket
from datetime import datetime, timezone, date as date_type

import pytest

from flask_restx import inputs
from flask_restx.inputs import (
    ipv4,
    ipv6,
    ip,
    URL,
    email,
    regex,
    _normalize_interval,
    _expand_datetime,
    _parse_interval,
    iso8601interval,
    date,
    _get_integer,
    natural,
    positive,
    int_range,
    boolean,
    datetime_from_rfc822,
    datetime_from_iso8601,
    date_from_iso8601,
)


# ---------------------------------------------------------------------------
# ipv4
# ---------------------------------------------------------------------------

class IPv4Test:
    def test_valid_ipv4(self):
        assert ipv4("192.168.1.1") == "192.168.1.1"

    def test_valid_ipv4_loopback(self):
        assert ipv4("127.0.0.1") == "127.0.0.1"

    def test_invalid_ipv4_raises(self):
        with pytest.raises(ValueError):
            ipv4("not-an-ip")

    def test_invalid_ipv4_too_few_octets(self):
        with pytest.raises(ValueError):
            ipv4("192.168.1")

    def test_ipv4_schema(self):
        assert ipv4.__schema__ == {"type": "string", "format": "ipv4"}


# ---------------------------------------------------------------------------
# ipv6
# ---------------------------------------------------------------------------

class IPv6Test:
    def test_valid_ipv6(self):
        assert ipv6("::1") == "::1"

    def test_valid_ipv6_full(self):
        assert ipv6("2001:db8::1") == "2001:db8::1"

    def test_invalid_ipv6_raises(self):
        with pytest.raises(ValueError):
            ipv6("not-ipv6")

    def test_ipv6_schema(self):
        assert ipv6.__schema__ == {"type": "string", "format": "ipv6"}


# ---------------------------------------------------------------------------
# ip
# ---------------------------------------------------------------------------

class IpTest:
    def test_valid_ipv4_via_ip(self):
        assert ip("10.0.0.1") == "10.0.0.1"

    def test_valid_ipv6_via_ip(self):
        assert ip("::1") == "::1"

    def test_invalid_ip_raises(self):
        with pytest.raises(ValueError):
            ip("not-an-ip")

    def test_ip_schema(self):
        assert ip.__schema__ == {"type": "string", "format": "ip"}


# ---------------------------------------------------------------------------
# URL
# ---------------------------------------------------------------------------

class URLTest:
    def test_init_defaults(self):
        u = URL()
        assert u.check is False
        assert u.ip is False
        assert u.local is False
        assert u.port is False
        assert u.auth is False
        assert u.schemes is None
        assert u.domains is None
        assert u.exclude is None

    def test_init_custom(self):
        u = URL(check=True, ip=True, local=True, port=True, auth=True,
                schemes=["https"], domains=["example.com"], exclude=["bad.com"])
        assert u.check is True
        assert u.schemes == ["https"]

    def test_error_raises_value_error(self):
        u = URL()
        with pytest.raises(ValueError, match="is not a valid URL"):
            u.error("bad")

    def test_error_with_details(self):
        u = URL()
        with pytest.raises(ValueError, match="Some detail"):
            u.error("bad", "Some detail")

    def test_valid_url(self):
        u = URL()
        assert u("http://example.com") == "http://example.com"

    def test_url_no_scheme_raises(self):
        u = URL()
        with pytest.raises(ValueError):
            u("example.com/path")

    def test_url_wrong_scheme_raises(self):
        u = URL(schemes=["https"])
        with pytest.raises(ValueError, match="Protocol is not allowed"):
            u("http://example.com")

    def test_url_with_ip_not_allowed(self):
        u = URL()
        with pytest.raises(ValueError, match="IP is not allowed"):
            u("http://192.168.1.1")

    def test_url_with_ip_allowed(self):
        u = URL(ip=True)
        assert u("http://192.168.1.1") == "http://192.168.1.1"

    def test_url_localhost_not_allowed(self):
        u = URL()
        with pytest.raises(ValueError, match="Localhost is not allowed"):
            u("http://localhost")

    def test_url_localhost_allowed(self):
        u = URL(local=True)
        assert u("http://localhost") == "http://localhost"

    def test_url_with_port_not_allowed(self):
        u = URL()
        with pytest.raises(ValueError, match="Custom port is not allowed"):
            u("http://example.com:8080")

    def test_url_with_port_allowed(self):
        u = URL(port=True)
        assert u("http://example.com:8080") == "http://example.com:8080"

    def test_url_port_out_of_range(self):
        u = URL(port=True)
        with pytest.raises(ValueError, match="Port is out of range"):
            u("http://example.com:65535")

    def test_url_auth_not_allowed(self):
        u = URL()
        with pytest.raises(ValueError, match="Authentication is not allowed"):
            u("http://user:pass@example.com")

    def test_url_auth_allowed(self):
        u = URL(auth=True)
        assert u("http://user:pass@example.com") == "http://user:pass@example.com"

    def test_url_domain_restriction(self):
        u = URL(domains=["allowed.com"])
        with pytest.raises(ValueError, match="Domain is not allowed"):
            u("http://other.com")

    def test_url_domain_allowed(self):
        u = URL(domains=["example.com"])
        assert u("http://example.com") == "http://example.com"

    def test_url_exclude_domain(self):
        u = URL(exclude=["bad.com"])
        with pytest.raises(ValueError, match="Domain is not allowed"):
            u("http://bad.com")

    def test_url_schema_property(self):
        u = URL()
        assert u.__schema__ == {"type": "string", "format": "url"}

    def test_url_ipv6_loopback_not_allowed(self):
        u = URL(ip=True)
        with pytest.raises(ValueError, match="Localhost is not allowed"):
            u("http://[::1]")

    def test_url_ipv6_loopback_allowed(self):
        u = URL(ip=True, local=True)
        assert u("http://[::1]") == "http://[::1]"

    def test_url_missing_netloc_suggests_http(self):
        u = URL()
        with pytest.raises(ValueError, match="Did you mean"):
            u("example.com")

    def test_url_bad_netloc_no_suggestion(self):
        u = URL()
        with pytest.raises(ValueError):
            u("://")

    def test_url_netloc_no_tld_raises(self):
        # netloc present but doesn't match netloc_regex (no TLD) → line 157
        u = URL()
        with pytest.raises(ValueError):
            u("http://invalidhost")

    def test_url_invalid_ip_value_raises(self):
        # IP matches regex pattern but fails ip() validation → lines 165-166
        u = URL(ip=True)
        with pytest.raises(ValueError):
            u("http://999.999.999.999")

    def test_url_ipv4_127_localhost_not_allowed(self):
        # IPv4 starting with 127. with ip=True but local=False → line 169
        u = URL(ip=True)
        with pytest.raises(ValueError, match="Localhost is not allowed"):
            u("http://127.0.0.1")

    def test_url_ip_with_check_true_passes(self):
        # Valid IP with check=True exercises the `if self.check: pass` branch → line 173
        u = URL(ip=True, check=True)
        assert u("http://8.8.8.8") == "http://8.8.8.8"

    def test_url_check_existing_domain(self, mocker):
        # check=True with resolvable domain → lines 191-192
        mocker.patch("flask_restx.inputs.socket.getaddrinfo", return_value=[])
        u = URL(check=True)
        assert u("http://example.com") == "http://example.com"

    def test_url_check_nonexistent_domain_raises(self, mocker):
        # check=True with unresolvable domain → lines 193-194
        mocker.patch(
            "flask_restx.inputs.socket.getaddrinfo",
            side_effect=socket.error("DNS failure"),
        )
        u = URL(check=True)
        with pytest.raises(ValueError, match="Domain does not exists"):
            u("http://nonexistent-domain-xyz.example")


# ---------------------------------------------------------------------------
# email
# ---------------------------------------------------------------------------

class EmailTest:
    def test_init_defaults(self):
        e = email()
        assert e.check is False
        assert e.ip is False
        assert e.local is False
        assert e.domains is None
        assert e.exclude is None

    def test_error_raises_value_error(self):
        e = email()
        with pytest.raises(ValueError, match="is not a valid email"):
            e.error("bad@email")

    def test_error_with_custom_msg(self):
        e = email()
        with pytest.raises(ValueError, match="Custom"):
            e.error("bad@email", "Custom {0}")

    def test_is_ip_true_for_ip(self):
        e = email()
        assert e.is_ip("192.168.1.1") is True

    def test_is_ip_false_for_non_ip(self):
        e = email()
        assert e.is_ip("example.com") is False

    def test_valid_email(self):
        e = email()
        assert e("user@example.com") == "user@example.com"

    def test_invalid_email_raises(self):
        e = email()
        with pytest.raises(ValueError):
            e("not-an-email")

    def test_email_double_dot_raises(self):
        e = email()
        with pytest.raises(ValueError):
            e("user..name@example.com")

    def test_email_domain_restriction(self):
        e = email(domains=["allowed.com"])
        with pytest.raises(ValueError):
            e("user@other.com")

    def test_email_domain_allowed(self):
        e = email(domains=["example.com"])
        assert e("user@example.com") == "user@example.com"

    def test_email_exclude_domain(self):
        e = email(exclude=["bad.com"])
        with pytest.raises(ValueError):
            e("user@bad.com")

    def test_email_localhost_not_allowed(self):
        e = email()
        with pytest.raises(ValueError):
            e("user@localhost")

    def test_email_localhost_allowed(self):
        e = email(local=True)
        assert e("user@localhost") == "user@localhost"

    def test_email_ip_not_allowed(self):
        e = email()
        with pytest.raises(ValueError):
            e("user@192.168.1.1")

    def test_email_ip_allowed(self):
        e = email(ip=True)
        assert e("user@192.168.1.1") == "user@192.168.1.1"

    def test_email_schema_property(self):
        e = email()
        assert e.__schema__ == {"type": "string", "format": "email"}

    def test_email_check_dns_valid(self, mocker):
        mocker.patch("socket.getaddrinfo", return_value=True)
        e = email(check=True)
        assert e("user@example.com") == "user@example.com"

    def test_email_check_dns_invalid(self, mocker):
        mocker.patch("socket.getaddrinfo", side_effect=socket.error("DNS failure"))
        e = email(check=True)
        with pytest.raises(ValueError):
            e("user@nonexistent-domain-xyz.com")


# ---------------------------------------------------------------------------
# regex
# ---------------------------------------------------------------------------

class RegexTest:
    def test_init(self):
        r = regex(r"^\d+$")
        assert r.pattern == r"^\d+$"

    def test_valid_match(self):
        r = regex(r"^\d+$")
        assert r("12345") == "12345"

    def test_invalid_match_raises(self):
        r = regex(r"^\d+$")
        with pytest.raises(ValueError, match='does not match pattern'):
            r("abc")

    def test_deepcopy(self):
        r = regex(r"^\d+$")
        r2 = copy.deepcopy(r)
        assert r2.pattern == r.pattern
        assert r2 is not r

    def test_schema(self):
        r = regex(r"^\d+$")
        assert r.__schema__ == {"type": "string", "pattern": r"^\d+$"}


# ---------------------------------------------------------------------------
# _normalize_interval
# ---------------------------------------------------------------------------

class NormalizeIntervalTest:
    def test_with_date_objects(self):
        import aniso8601
        d1 = aniso8601.parse_date("2013-01-01")
        d2 = aniso8601.parse_date("2013-01-02")
        start, end = _normalize_interval(d1, d2, "2013-01-01/2013-01-02")
        assert isinstance(start, datetime)
        assert start.tzinfo is not None

    def test_with_naive_datetime(self):
        start_dt = datetime(2013, 1, 1, 12, 0, 0)
        end_dt = datetime(2013, 1, 1, 13, 0, 0)
        start, end = _normalize_interval(start_dt, end_dt, "some-value")
        assert start.tzinfo == timezone.utc
        assert end.tzinfo == timezone.utc

    def test_with_aware_datetime(self):
        import aniso8601
        start_dt = aniso8601.parse_datetime("2013-01-01T12:00:00+02:00")
        end_dt = aniso8601.parse_datetime("2013-01-01T13:00:00+02:00")
        start, end = _normalize_interval(start_dt, end_dt, "some-value")
        assert start.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# _expand_datetime
# ---------------------------------------------------------------------------

class ExpandDatetimeTest:
    def test_with_date_object(self):
        import aniso8601
        d = aniso8601.parse_date("2013-01-01")
        end = _expand_datetime(d, "2013-01-01")
        from datetime import timedelta
        expected = datetime(2013, 1, 2)
        assert end == d + timedelta(days=1)

    def test_datetime_hour_resolution(self):
        dt = datetime(2013, 1, 1, 12)
        end = _expand_datetime(dt, "2013-01-01T12")
        from datetime import timedelta
        assert end == dt + timedelta(hours=1)

    def test_datetime_minute_resolution(self):
        dt = datetime(2013, 1, 1, 12, 0)
        end = _expand_datetime(dt, "2013-01-01T12:00")
        from datetime import timedelta
        assert end == dt + timedelta(minutes=1)

    def test_datetime_second_resolution(self):
        dt = datetime(2013, 1, 1, 12, 0, 0)
        end = _expand_datetime(dt, "2013-01-01T12:00:00")
        from datetime import timedelta
        assert end == dt + timedelta(seconds=1)


# ---------------------------------------------------------------------------
# _parse_interval
# ---------------------------------------------------------------------------

class ParseIntervalTest:
    def test_full_interval(self):
        start, end = _parse_interval("2013-01-01/2013-01-02")
        assert start is not None
        assert end is not None

    def test_single_datetime(self):
        start, end = _parse_interval("2013-01-01T12:00:00")
        assert start is not None
        assert end is None

    def test_single_date(self):
        start, end = _parse_interval("2013-01-01")
        assert start is not None
        assert end is None


# ---------------------------------------------------------------------------
# iso8601interval
# ---------------------------------------------------------------------------

class Iso8601IntervalTest:
    def test_empty_value_raises(self):
        with pytest.raises(ValueError):
            iso8601interval("")

    def test_single_date(self):
        start, end = iso8601interval("2013-01-01")
        assert start == datetime(2013, 1, 1, tzinfo=timezone.utc)
        assert end == datetime(2013, 1, 2, tzinfo=timezone.utc)

    def test_full_interval(self):
        start, end = iso8601interval("2013-01-01/2013-02-01")
        assert start.year == 2013
        assert end.month == 2

    def test_duration_interval(self):
        start, end = iso8601interval("2013-01-01/P3D")
        assert (end - start).days == 3

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            iso8601interval("not-a-date")

    def test_datetime_hour_resolution(self):
        start, end = iso8601interval("2013-01-01T12")
        from datetime import timedelta
        assert end - start == timedelta(hours=1)

    def test_datetime_minute_resolution(self):
        start, end = iso8601interval("2013-01-01T12:00")
        from datetime import timedelta
        assert end - start == timedelta(minutes=1)

    def test_iso8601interval_schema(self):
        assert iso8601interval.__schema__ == {"type": "string", "format": "iso8601-interval"}


# ---------------------------------------------------------------------------
# date
# ---------------------------------------------------------------------------

class DateTest:
    def test_valid_date(self):
        result = date("2013-01-01")
        assert result == datetime(2013, 1, 1)

    def test_invalid_date_raises(self):
        with pytest.raises(ValueError):
            date("not-a-date")

    def test_date_schema(self):
        assert date.__schema__ == {"type": "string", "format": "date"}


# ---------------------------------------------------------------------------
# _get_integer
# ---------------------------------------------------------------------------

class GetIntegerTest:
    def test_valid_integer_string(self):
        assert _get_integer("42") == 42

    def test_valid_integer(self):
        assert _get_integer(42) == 42

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="is not a valid integer"):
            _get_integer("abc")

    def test_none_raises(self):
        with pytest.raises(ValueError):
            _get_integer(None)


# ---------------------------------------------------------------------------
# natural
# ---------------------------------------------------------------------------

class NaturalTest:
    def test_zero_is_natural(self):
        assert natural(0) == 0

    def test_positive_is_natural(self):
        assert natural(5) == 5

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            natural(-1)

    def test_natural_schema(self):
        assert natural.__schema__ == {"type": "integer", "minimum": 0}


# ---------------------------------------------------------------------------
# positive
# ---------------------------------------------------------------------------

class PositiveTest:
    def test_positive_integer(self):
        assert positive(1) == 1

    def test_zero_raises(self):
        with pytest.raises(ValueError, match="positive integer"):
            positive(0)

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="positive integer"):
            positive(-1)

    def test_positive_schema(self):
        assert positive.__schema__ == {"type": "integer", "minimum": 0, "exclusiveMinimum": True}


# ---------------------------------------------------------------------------
# int_range
# ---------------------------------------------------------------------------

class IntRangeTest:
    def test_init(self):
        r = int_range(1, 10)
        assert r.low == 1
        assert r.high == 10
        assert r.argument == "argument"

    def test_value_in_range(self):
        r = int_range(1, 10)
        assert r(5) == 5

    def test_value_below_range_raises(self):
        r = int_range(1, 10)
        with pytest.raises(ValueError, match="within the range"):
            r(0)

    def test_value_above_range_raises(self):
        r = int_range(1, 10)
        with pytest.raises(ValueError, match="within the range"):
            r(11)

    def test_boundary_low(self):
        r = int_range(1, 10)
        assert r(1) == 1

    def test_boundary_high(self):
        r = int_range(1, 10)
        assert r(10) == 10

    def test_schema(self):
        r = int_range(1, 10)
        assert r.__schema__ == {"type": "integer", "minimum": 1, "maximum": 10}


# ---------------------------------------------------------------------------
# boolean
# ---------------------------------------------------------------------------

class BooleanTest:
    def test_bool_true_passthrough(self):
        assert boolean(True) is True

    def test_bool_false_passthrough(self):
        assert boolean(False) is False

    def test_none_raises(self):
        with pytest.raises(ValueError, match="non-null"):
            boolean(None)

    def test_empty_string_returns_false(self):
        assert boolean("") is False

    def test_string_true(self):
        assert boolean("true") is True

    def test_string_True_case_insensitive(self):
        assert boolean("True") is True

    def test_string_1(self):
        assert boolean("1") is True

    def test_string_on(self):
        assert boolean("on") is True

    def test_string_false(self):
        assert boolean("false") is False

    def test_string_0(self):
        assert boolean("0") is False

    def test_string_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid literal"):
            boolean("maybe")

    def test_boolean_schema(self):
        assert boolean.__schema__ == {"type": "boolean"}


# ---------------------------------------------------------------------------
# datetime_from_rfc822
# ---------------------------------------------------------------------------

class DatetimeFromRfc822Test:
    def test_valid_rfc822(self):
        result = datetime_from_rfc822("Wed, 02 Oct 2002 08:00:00 EST")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_rfc822_without_time(self):
        result = datetime_from_rfc822("02 Oct 2002")
        assert isinstance(result, datetime)

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid date literal"):
            datetime_from_rfc822("not-a-date")

    def test_rfc822_with_timezone(self):
        result = datetime_from_rfc822("Wed, 02 Oct 2002 08:00:00 +0000")
        assert result.tzinfo is not None


# ---------------------------------------------------------------------------
# datetime_from_iso8601
# ---------------------------------------------------------------------------

class DatetimeFromIso8601Test:
    def test_valid_datetime(self):
        result = datetime_from_iso8601("2012-01-01T23:30:00+02:00")
        assert isinstance(result, datetime)

    def test_valid_date_only(self):
        result = datetime_from_iso8601("2012-01-01")
        assert result == datetime(2012, 1, 1)

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid date literal"):
            datetime_from_iso8601("not-a-date")

    def test_iso8601_schema(self):
        assert datetime_from_iso8601.__schema__ == {"type": "string", "format": "date-time"}


# ---------------------------------------------------------------------------
# date_from_iso8601
# ---------------------------------------------------------------------------

class DateFromIso8601Test:
    def test_valid_date(self):
        result = date_from_iso8601("2012-01-01")
        assert result == date_type(2012, 1, 1)

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            date_from_iso8601("not-a-date")

    def test_schema(self):
        assert date_from_iso8601.__schema__ == {"type": "string", "format": "date"}
