import pytest

from app.paging import page_slice


@pytest.mark.parametrize(
    ("page", "expected"),
    [(1, ["a", "b"]), (2, ["c", "d"]), (3, ["e"])],
)
def test_page_slice(page: int, expected: list[str]) -> None:
    assert page_slice(["a", "b", "c", "d", "e"], page, 2) == expected
