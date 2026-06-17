"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── query parsing ─────────────────────────────────────────────────────────────

# Common size tokens we expect users to type (letter sizes, numeric, waist/US).
_SIZE_PATTERNS = [
    r"\bone\s*size\b",
    r"\b(?:US|UK|EU)?\d{1,2}(?:\.\d)?\b",   # US8.5, 28, 10
    r"\bW\d{2}(?:\s*L\d{2})?\b",             # W28, W28 L30
    r"\b(?:XXS|XS|S|M|L|XL|XXL|XXXL)\b",     # letter sizes
]


def _parse_query(query: str) -> dict:
    """
    Extract a description, size, and max_price from a natural language query.

    Uses lightweight regex/string parsing (no LLM call) so query parsing stays
    fast, deterministic, and free. The leftover text — after price and size
    phrases are stripped — becomes the keyword description handed to
    search_listings(), which already does its own keyword scoring.
    """
    remaining = query or ""
    size = None
    max_price = None

    # 1. Explicit "size X" phrase first, so its digits (e.g. "W28") can't be
    #    mistaken for a price below.
    size_phrase = re.search(r"\bsize\s+([A-Za-z0-9./]+)\b", remaining, re.IGNORECASE)
    if size_phrase:
        size = size_phrase.group(1).upper()
        remaining = remaining.replace(size_phrase.group(0), " ")

    # 2. Price ceiling — only when an explicit marker (under/below/$/…) is
    #    present, so a bare size number like "28" never reads as a price.
    price_match = re.search(
        r"(?:(?:under|below|less than|max(?:imum)?|up to)\s*\$?\s*|\$\s*)"
        r"(\d+(?:\.\d{1,2})?)\s*(?:dollars|usd|bucks)?",
        remaining,
        re.IGNORECASE,
    )
    if price_match:
        max_price = float(price_match.group(1))
        remaining = remaining.replace(price_match.group(0), " ")

    # 3. If no explicit "size X" phrase, look for a standalone size token.
    if size is None:
        for pattern in _SIZE_PATTERNS:
            m = re.search(pattern, remaining, re.IGNORECASE)
            if m:
                size = m.group(0).strip().upper()
                remaining = remaining.replace(m.group(0), " ")
                break

    # 4. Whatever remains is the keyword description.
    description = re.sub(r"\s+", " ", remaining).strip()

    return {"description": description, "size": size, "max_price": max_price}


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # Step 1: fresh session — the single source of truth for this run.
    session = _new_session(query, wardrobe)

    # Step 2: parse the query into description / size / max_price.
    session["parsed"] = _parse_query(query)
    description = session["parsed"]["description"]
    size = session["parsed"]["size"]
    max_price = session["parsed"]["max_price"]

    # Step 3: search listings. Short-circuit if nothing matches — the
    # remaining tools have nothing to work with.
    session["search_results"] = search_listings(description, size, max_price)
    if not session["search_results"]:
        constraints = []
        if size:
            constraints.append(f"size {size}")
        if max_price is not None:
            constraints.append(f"under ${max_price:.0f}")
        detail = f" ({', '.join(constraints)})" if constraints else ""
        session["error"] = (
            f"No listings matched \"{description}\"{detail}. "
            "Try loosening the size or price, or different keywords."
        )
        return session

    # Step 4: take the top-scoring match as the item to style.
    session["selected_item"] = session["search_results"][0]

    # Step 5: suggest an outfit pairing the item with the wardrobe.
    #         suggest_outfit() always returns a non-empty string (it falls back
    #         to general styling advice for an empty wardrobe).
    session["outfit_suggestion"] = suggest_outfit(
        session["selected_item"], wardrobe
    )

    # Step 6: turn the outfit into a shareable fit card.
    session["fit_card"] = create_fit_card(
        session["outfit_suggestion"], session["selected_item"]
    )

    # Step 7: done — return the completed session.
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
