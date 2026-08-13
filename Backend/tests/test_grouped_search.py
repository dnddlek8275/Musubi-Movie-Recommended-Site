from datetime import date
from types import SimpleNamespace

from app.services.movies.search_service import _normalized_text, _recent_movie_rows


def test_normalized_text_ignores_spaces_and_case():
    assert _normalized_text(" Mission Impossible ") == "missionimpossible"
    assert _normalized_text("미션 임파서블") == "미션임파서블"


def test_recent_movie_rows_orders_by_release_date(monkeypatch):
    captured = {}

    class FakeScalars:
        def all(self):
            return [
                SimpleNamespace(id=2, title="최근 영화", release_date=date(2026, 1, 1)),
                SimpleNamespace(id=1, title="이전 영화", release_date=date(2025, 1, 1)),
            ]

    class FakeDb:
        def scalars(self, statement):
            captured["statement"] = statement
            return FakeScalars()

    rows, has_more = _recent_movie_rows(FakeDb(), True, 20)

    assert [row.id for row in rows] == [2, 1]
    assert has_more is False
    statement_text = str(captured["statement"])
    assert "movies.release_date DESC NULLS LAST" in statement_text
    assert "LIMIT" in statement_text


def test_recent_movie_rows_requests_one_extra_row_for_has_more():
    class FakeScalars:
        def all(self):
            return [SimpleNamespace(id=index, title=str(index)) for index in range(1, 4)]

    class FakeDb:
        def scalars(self, statement):
            return FakeScalars()

    rows, has_more = _recent_movie_rows(FakeDb(), True, 2, page=2)

    assert [row.id for row in rows] == [1, 2]
    assert has_more is True
