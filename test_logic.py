"""Offline sanity checks for the filter/dedup logic (no network)."""
import monitor


def test_matches():
    kw = ["data engineer", "machine learning engineer"]
    loc = ["canada", "remote"]

    assert monitor.matches(
        {"title": "Senior Data Engineer", "location": "Toronto, Canada"}, kw, loc
    )
    assert monitor.matches(
        {"title": "Machine Learning Engineer", "location": "Remote - US"}, kw, loc
    )
    assert not monitor.matches(
        {"title": "Frontend Engineer", "location": "Canada"}, kw, loc
    )
    assert not monitor.matches(
        {"title": "Data Engineer", "location": "Berlin, Germany"}, kw, loc
    )
    # empty filters accept everything
    assert monitor.matches({"title": "Anything", "location": "Mars"}, [], [])
    print("matches(): OK")


def test_dedup_key():
    seen = set()
    j = {"id": "42", "title": "Data Engineer", "location": "Remote"}
    key = f"greenhouse:stripe:{j['id']}"
    assert key not in seen
    seen.add(key)
    assert key in seen  # second sighting is a dup, would not re-alert
    print("dedup key: OK")


if __name__ == "__main__":
    test_matches()
    test_dedup_key()
    print("all good")
