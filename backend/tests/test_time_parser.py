"""Unit tests for parse_time_range covering all supported formats."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.utils.time_parser import parse_time_range, parse_time_token, TimeRange


class TestParseTimeToken:
    def test_seconds_short(self):
        assert parse_time_token("30s") == 30.0

    def test_seconds_long(self):
        assert parse_time_token("30sec") == 30.0
        assert parse_time_token("30 seconds") == 30.0

    def test_minutes_short(self):
        assert parse_time_token("2m") == 120.0

    def test_minutes_long(self):
        assert parse_time_token("2min") == 120.0
        assert parse_time_token("2 minutes") == 120.0

    def test_colon_mm_ss(self):
        assert parse_time_token("1:30") == 90.0
        assert parse_time_token("0:20") == 20.0
        assert parse_time_token("2:00") == 120.0

    def test_colon_hh_mm_ss(self):
        assert parse_time_token("1:00:00") == 3600.0
        assert parse_time_token("0:01:30") == 90.0

    def test_combined_min_sec(self):
        assert parse_time_token("1m30s") == 90.0
        assert parse_time_token("1m 30s") == 90.0

    def test_plain_number(self):
        assert parse_time_token("90") == 90.0

    def test_float_seconds(self):
        assert parse_time_token("14.5s") == 14.5

    def test_invalid(self):
        assert parse_time_token("abc") is None
        assert parse_time_token("") is None


class TestParseTimeRange:
    def test_sec_to_sec(self):
        r = parse_time_range("10 sec to 20 sec")
        assert r is not None
        assert r.start == 10.0
        assert r.end == 20.0

    def test_colon_dash(self):
        r = parse_time_range("0:10-0:20")
        assert r is not None
        assert r.start == 10.0
        assert r.end == 20.0

    def test_colon_to_colon(self):
        r = parse_time_range("1:30 to 2:00")
        assert r is not None
        assert r.start == 90.0
        assert r.end == 120.0

    def test_from_to_plain_seconds(self):
        r = parse_time_range("from 90s to 120s")
        assert r is not None
        assert r.start == 90.0
        assert r.end == 120.0

    def test_minute_n(self):
        r = parse_time_range("minute 2")
        assert r is not None
        assert r.start == 60.0
        assert r.end == 120.0

    def test_the_beginning(self):
        r = parse_time_range("what happens at the beginning?", video_duration=300.0)
        assert r is not None
        assert r.start == 0.0
        assert r.end > 0.0

    def test_the_end(self):
        r = parse_time_range("summarize the end", video_duration=300.0)
        assert r is not None
        assert r.start == 270.0
        assert r.end == 300.0

    def test_last_30_seconds(self):
        r = parse_time_range("what happened in the last 30 seconds?", video_duration=120.0)
        assert r is not None
        assert r.start == 90.0
        assert r.end == 120.0

    def test_first_minute(self):
        r = parse_time_range("summarize the first minute")
        assert r is not None
        assert r.start == 0.0
        assert r.end == 60.0

    def test_between_and(self):
        r = parse_time_range("between 1:00 and 1:30")
        assert r is not None
        assert r.start == 60.0
        assert r.end == 90.0

    def test_no_range_general_question(self):
        r = parse_time_range("what are the main topics?")
        assert r is None

    def test_natural_query_with_range(self):
        r = parse_time_range("What did she say from 30s to 60s?")
        assert r is not None
        assert r.start == 30.0
        assert r.end == 60.0

    def test_range_plain_seconds(self):
        r = parse_time_range("10 to 30")
        assert r is not None
        assert r.start == 10.0
        assert r.end == 30.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
