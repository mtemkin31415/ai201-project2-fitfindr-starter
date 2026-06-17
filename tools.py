"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # 1. Filter by price ceiling (inclusive) and size, when those are provided.
    candidates = []
    for item in listings:
        if max_price is not None and item.get("price", 0) > max_price:
            continue
        if size is not None and not _size_matches(size, item.get("size", "")):
            continue
        candidates.append(item)

    # 2. Score each remaining listing by keyword overlap with the description.
    query_keywords = _tokenize(description)
    scored = []
    for item in candidates:
        score = _score_listing(query_keywords, item)
        if score > 0:  # 3. Drop listings with no relevant matches.
            scored.append((score, item))

    # 4. Sort by score, highest first, and return the listing dicts.
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]


# ── Tool 1 helpers ──────────────────────────────────────────────────────────

def _tokenize(text: str) -> set[str]:
    """Lowercase a string and split it into a set of alphanumeric word tokens."""
    if not text:
        return set()
    cleaned = "".join(ch if ch.isalnum() else " " for ch in text.lower())
    return {tok for tok in cleaned.split() if tok}


def _size_matches(query_size: str, item_size: str) -> bool:
    """
    Case-insensitive size match. Returns True if the query size appears as a
    whole token within the listing's size string, so "M" matches "S/M" and
    "W28" matches "W28 L30", but "M" does not match "XL".
    """
    if not query_size:
        return True
    return _tokenize(query_size).issubset(_tokenize(item_size))


def _score_listing(query_keywords: set[str], item: dict) -> int:
    """
    Count how many query keywords overlap with the listing's searchable text:
    its title, description, style_tags, colors, and category.
    """
    haystack = _tokenize(item.get("title", ""))
    haystack |= _tokenize(item.get("description", ""))
    haystack |= _tokenize(item.get("category", ""))
    for tag in item.get("style_tags", []):
        haystack |= _tokenize(tag)
    for color in item.get("colors", []):
        haystack |= _tokenize(color)
    return len(query_keywords & haystack)


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    client = _get_groq_client()
    item_desc = _describe_item(new_item)

    # Empty wardrobe → general styling advice instead of specific combinations.
    items = wardrobe.get("items", []) if isinstance(wardrobe, dict) else []
    if not items:
        prompt = (
            f"A shopper is considering this thrifted item:\n{item_desc}\n\n"
            "They haven't shared their wardrobe yet. Suggest how to style this "
            "piece in general: what kinds of items pair well with it, what vibe "
            "it suits, and 1-2 example outfit ideas. Keep it friendly and "
            "concise (a short paragraph)."
        )
    else:
        wardrobe_desc = "\n".join(f"- {_describe_wardrobe_item(it)}" for it in items)
        prompt = (
            f"A shopper is considering this thrifted item:\n{item_desc}\n\n"
            f"Here is what's already in their wardrobe:\n{wardrobe_desc}\n\n"
            "Suggest 1-2 complete outfits that pair the thrifted item with "
            "specific pieces from their wardrobe. Each outfit should use 2-4 "
            "items total (including the thrifted item) and name the wardrobe "
            "pieces you're using. Briefly explain why each outfit works. Keep "
            "it concise."
        )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are FitFindr, a friendly thrift-styling assistant. "
                    "You give practical, specific outfit advice."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


# ── Tool 2 helpers ──────────────────────────────────────────────────────────

def _describe_item(item: dict) -> str:
    """Format a listing dict into a one-line description for an LLM prompt."""
    title = item.get("title") or item.get("name") or "Unknown item"
    parts = [title]
    if item.get("category"):
        parts.append(f"({item['category']})")
    if item.get("colors"):
        parts.append("colors: " + ", ".join(item["colors"]))
    if item.get("style_tags"):
        parts.append("style: " + ", ".join(item["style_tags"]))
    if item.get("description"):
        parts.append(f"— {item['description']}")
    return " ".join(parts)


def _describe_wardrobe_item(item: dict) -> str:
    """Format a wardrobe item dict into a one-line description for a prompt."""
    name = item.get("name") or item.get("title") or "Unknown item"
    parts = [name]
    if item.get("category"):
        parts.append(f"({item['category']})")
    if item.get("colors"):
        parts.append("colors: " + ", ".join(item["colors"]))
    if item.get("notes"):
        parts.append(f"— {item['notes']}")
    return " ".join(parts)


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # 1. Guard against an empty / whitespace-only outfit — return an error
    #    message string rather than crashing or calling the LLM with nothing.
    if not outfit or not outfit.strip():
        return (
            "Sorry, I can't make a fit card without an outfit to describe. "
            "Want help putting one together or finding other pieces first?"
        )

    client = _get_groq_client()
    item_desc = _describe_item(new_item)

    # Pull the details the caption should mention naturally (once each).
    item_name = new_item.get("title") or new_item.get("name") or "this thrifted find"
    price = new_item.get("price")
    price_str = f"${price:.0f}" if isinstance(price, (int, float)) else "a steal"
    platform = new_item.get("platform") or "online"

    # 2. Build the prompt with the item details and the suggested outfit.
    prompt = (
        f"Here is a thrifted item someone scored:\n{item_desc}\n"
        f"- name: {item_name}\n"
        f"- price: {price_str}\n"
        f"- platform: {platform}\n\n"
        f"Here is the outfit they're wearing it with:\n{outfit.strip()}\n\n"
        "Write a short, shareable social-media caption (2-4 sentences) for an "
        "OOTD post about this look. Requirements:\n"
        "- Sound casual and authentic, like a real outfit-of-the-day post, "
        "not a product description.\n"
        f"- Mention the item name ({item_name}), the price ({price_str}), and "
        f"the platform ({platform}) naturally — once each.\n"
        "- Capture the specific vibe of the outfit.\n"
        "Return only the caption text, no preamble."
    )

    # 3. Call the LLM. Higher temperature so captions vary across runs.
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are FitFindr, a friendly thrift-styling assistant who "
                    "writes punchy, authentic social-media captions."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=1.1,
    )
    return response.choices[0].message.content.strip()
