"""
tests/test_tools.py

Pytest suite for the three FitFindr tools. Each tool has at least one test
per failure mode described in planning.md's Error Handling table:

    search_listings  → no results match the query         (returns [])
    suggest_outfit   → wardrobe is empty                   (general advice)
    create_fit_card  → outfit input missing / incomplete   (error string)

The two LLM-backed tools (suggest_outfit, create_fit_card) are tested against
a fake Groq client so the suite is deterministic and never hits the network.
"""

import pytest

import tools
from tools import create_fit_card, search_listings, suggest_outfit


# ── Fake Groq client ──────────────────────────────────────────────────────────
#
# Mirrors only the bits the tools touch:
#   client.chat.completions.create(...).choices[0].message.content


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, recorder):
        self._recorder = recorder

    def create(self, **kwargs):
        # Record the call so tests can assert on model/temperature/messages.
        self._recorder.append(kwargs)
        return _FakeResponse("  Fake LLM caption about the look.  ")


class _FakeChat:
    def __init__(self, recorder):
        self.completions = _FakeCompletions(recorder)


class _FakeGroqClient:
    def __init__(self, recorder):
        self.chat = _FakeChat(recorder)


@pytest.fixture
def fake_llm(monkeypatch):
    """
    Patch tools._get_groq_client to return a fake client. Yields the list of
    recorded create() call kwargs so tests can inspect how the LLM was called.
    """
    calls = []
    monkeypatch.setattr(tools, "_get_groq_client", lambda: _FakeGroqClient(calls))
    return calls


# ── Fixtures: sample data ─────────────────────────────────────────────────────


@pytest.fixture
def sample_item():
    return {
        "title": "Vintage Band Tee",
        "category": "tops",
        "colors": ["black"],
        "style_tags": ["vintage", "grunge"],
        "description": "Faded 90s rock band tee, soft cotton",
        "price": 24.0,
        "platform": "depop",
    }


@pytest.fixture
def sample_wardrobe():
    return {
        "items": [
            {"name": "Baggy Blue Jeans", "category": "bottoms", "colors": ["blue"]},
            {"name": "Chunky White Sneakers", "category": "shoes", "colors": ["white"]},
        ]
    }


# ── Tool 1: search_listings ───────────────────────────────────────────────────


def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    # Failure mode: no listings match the query → empty list, never raises.
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    # Size matching is case-insensitive and token-based ("m" matches "S/M").
    results = search_listings("shirt", size="M", max_price=None)
    assert all(
        "m" in tools._tokenize(item.get("size", "")) for item in results
    )


def test_search_results_sorted_by_relevance():
    # Higher keyword overlap should rank first; scores are non-increasing.
    results = search_listings("vintage denim jacket", size=None, max_price=None)
    query = tools._tokenize("vintage denim jacket")
    scores = [tools._score_listing(query, item) for item in results]
    assert scores == sorted(scores, reverse=True)
    assert all(s > 0 for s in scores)  # zero-score items are dropped


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────


def test_suggest_outfit_empty_wardrobe(fake_llm, sample_item):
    # Failure mode: empty wardrobe → general styling advice, non-empty string,
    # and never raises.
    result = suggest_outfit(sample_item, {"items": []})
    assert isinstance(result, str)
    assert result  # non-empty
    # The general-advice branch should mention the user hasn't shared a wardrobe.
    prompt = fake_llm[0]["messages"][-1]["content"]
    assert "haven't shared their wardrobe" in prompt


def test_suggest_outfit_missing_items_key(fake_llm, sample_item):
    # A wardrobe dict with no 'items' key is treated as empty, not a crash.
    result = suggest_outfit(sample_item, {})
    assert isinstance(result, str) and result


def test_suggest_outfit_with_wardrobe(fake_llm, sample_item, sample_wardrobe):
    result = suggest_outfit(sample_item, sample_wardrobe)
    assert isinstance(result, str) and result
    prompt = fake_llm[0]["messages"][-1]["content"]
    # Specific-combinations branch should include the wardrobe pieces by name.
    assert "Baggy Blue Jeans" in prompt


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────


def test_fit_card_empty_outfit(sample_item):
    # Failure mode: empty outfit → descriptive error string, no exception, and
    # the LLM is never called (so no fake_llm fixture needed).
    result = create_fit_card("", sample_item)
    assert isinstance(result, str)
    assert "can't make a fit card" in result.lower()


def test_fit_card_whitespace_outfit(sample_item):
    # Whitespace-only counts as empty and hits the same guard.
    result = create_fit_card("   \n\t ", sample_item)
    assert "can't make a fit card" in result.lower()


def test_fit_card_valid(fake_llm, sample_item):
    outfit = "Vintage band tee with baggy jeans and chunky sneakers."
    result = create_fit_card(outfit, sample_item)
    assert isinstance(result, str) and result
    assert result == result.strip()  # response is stripped


def test_fit_card_uses_higher_temperature(fake_llm, sample_item):
    # Captions should vary run-to-run, so temperature must exceed the default
    # styling temperature (0.7) used by suggest_outfit.
    create_fit_card("a real outfit", sample_item)
    assert fake_llm[0]["temperature"] > 0.7
