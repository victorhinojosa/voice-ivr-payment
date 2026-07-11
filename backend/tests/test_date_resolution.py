"""
Unit tests for resolve_date_phrase / format_date_spoken (backend/dates.py).

All frozen instants use 12:00:00 UTC so that conversion to LOCAL_TZ
(America/Mexico_City, UTC-6) never crosses a local day boundary.
2026-07-10 is a Friday.
"""
from datetime import date

import pytest
from freezegun import freeze_time

from conversation.dates import resolve_date_phrase, format_date_spoken

FROZEN_FRIDAY = "2026-07-10 12:00:00"  # local: Friday, July 10 2026


# ---------------------------------------------------------------------------
# resolve_date_phrase — English
# ---------------------------------------------------------------------------

class TestResolveDatePhraseEnglish:
    def test_weekday_phrase_upcoming(self):
        with freeze_time(FROZEN_FRIDAY):
            assert resolve_date_phrase("next monday") == date(2026, 7, 13)

    def test_weekday_phrase_same_as_today_rolls_to_next_week(self):
        with freeze_time(FROZEN_FRIDAY):
            assert resolve_date_phrase("friday") == date(2026, 7, 17)

    def test_next_x_phrase(self):
        with freeze_time(FROZEN_FRIDAY):
            assert resolve_date_phrase("next week") == date(2026, 7, 17)

    def test_relative_duration_days(self):
        with freeze_time(FROZEN_FRIDAY):
            assert resolve_date_phrase("in 3 days") == date(2026, 7, 13)

    def test_relative_duration_weeks(self):
        with freeze_time(FROZEN_FRIDAY):
            assert resolve_date_phrase("in 2 weeks") == date(2026, 7, 24)

    def test_explicit_month_day(self):
        with freeze_time(FROZEN_FRIDAY):
            assert resolve_date_phrase("august 15th") == date(2026, 8, 15)

    def test_end_of_month_idiom(self):
        with freeze_time(FROZEN_FRIDAY):
            assert resolve_date_phrase("end of the month") == date(2026, 7, 31)

    def test_end_of_month_idiom_december_rolls_to_dec_31(self):
        with freeze_time("2026-12-05 12:00:00"):
            assert resolve_date_phrase("end of the month") == date(2026, 12, 31)

    def test_unparseable_phrase_returns_none(self):
        with freeze_time(FROZEN_FRIDAY):
            assert resolve_date_phrase("asdkjaslkdj") is None

    def test_empty_string_returns_none(self):
        assert resolve_date_phrase("") is None

    def test_none_returns_none(self):
        assert resolve_date_phrase(None) is None

    def test_parser_exception_is_swallowed_and_returns_none(self, monkeypatch):
        import conversation.dates

        def _raise(*args, **kwargs):
            raise ValueError("boom")

        monkeypatch.setattr(conversation.dates._CAL, "parseDT", _raise)
        with freeze_time(FROZEN_FRIDAY):
            assert resolve_date_phrase("next monday") is None


# ---------------------------------------------------------------------------
# resolve_date_phrase — Spanish
# ---------------------------------------------------------------------------

class TestResolveDatePhraseSpanish:
    def test_weekday_phrase(self):
        with freeze_time(FROZEN_FRIDAY):
            assert resolve_date_phrase("próximo lunes", "Spanish") == date(2026, 7, 13)

    def test_tomorrow(self):
        with freeze_time(FROZEN_FRIDAY):
            assert resolve_date_phrase("mañana", "Spanish") == date(2026, 7, 11)

    def test_day_after_tomorrow_idiom(self):
        with freeze_time(FROZEN_FRIDAY):
            assert resolve_date_phrase("pasado mañana", "Spanish") == date(2026, 7, 12)

    def test_next_week_phrase(self):
        with freeze_time(FROZEN_FRIDAY):
            assert resolve_date_phrase("próxima semana", "Spanish") == date(2026, 7, 17)

    def test_quincena_maps_to_15_days(self):
        with freeze_time(FROZEN_FRIDAY):
            assert resolve_date_phrase("en una quincena", "Spanish") == date(2026, 7, 25)

    def test_explicit_month_day(self):
        with freeze_time(FROZEN_FRIDAY):
            assert resolve_date_phrase("15 de agosto", "Spanish") == date(2026, 8, 15)

    def test_end_of_month_idiom_fin_de_mes(self):
        with freeze_time(FROZEN_FRIDAY):
            assert resolve_date_phrase("fin de mes", "Spanish") == date(2026, 7, 31)

    def test_end_of_month_idiom_final_del_mes(self):
        with freeze_time(FROZEN_FRIDAY):
            assert resolve_date_phrase("a finales del mes", "Spanish") == date(2026, 7, 31)

    def test_unparseable_phrase_returns_none(self):
        with freeze_time(FROZEN_FRIDAY):
            assert resolve_date_phrase("blablabla sin sentido", "Spanish") is None


# ---------------------------------------------------------------------------
# format_date_spoken
# ---------------------------------------------------------------------------

class TestFormatDateSpoken:
    @pytest.mark.parametrize(
        "day, expected_suffix",
        [
            (1, "1st"),
            (2, "2nd"),
            (3, "3rd"),
            (4, "4th"),
            (11, "11th"),
            (12, "12th"),
            (13, "13th"),
            (21, "21st"),
            (22, "22nd"),
            (23, "23rd"),
        ],
    )
    def test_english_ordinal_suffixes(self, day, expected_suffix):
        result = format_date_spoken(date(2026, 7, day))
        assert result.endswith(expected_suffix)

    def test_english_format_full(self):
        assert format_date_spoken(date(2026, 7, 10)) == "Friday, July 10th"

    def test_spanish_format_full(self):
        assert format_date_spoken(date(2026, 7, 10), "Spanish") == "viernes, 10 de julio"

    def test_spanish_format_uses_no_ordinal(self):
        result = format_date_spoken(date(2026, 7, 1), "Spanish")
        assert result == "miércoles, 1 de julio"
