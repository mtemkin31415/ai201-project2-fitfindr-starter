# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```

## Setup

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows:**
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Tool Inventory

Three tools, all defined in `tools.py`. Signatures below match the code exactly.

### Tool 1 — `search_listings`

- **Purpose:** Search the 40 mock listings for items matching the user's keywords, with optional size and price filters. This is the only tool that reads `listings.json`; every later tool works off the item it returns.
- **Inputs:**
  - `description` (`str`) — keywords describing the wanted item (e.g. `"vintage graphic tee"`).
  - `size` (`str | None`, default `None`) — size to filter by; case-insensitive token match, so `"M"` matches `"S/M"`. `None` skips size filtering.
  - `max_price` (`float | None`, default `None`) — inclusive price ceiling. `None` skips price filtering.
- **Output:** `list[dict]` — matching listing dicts sorted by keyword-overlap score, best first. Returns an empty list (never raises) when nothing matches. Each dict has: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand`, `platform`.

### Tool 2 — `suggest_outfit`

- **Purpose:** Given the chosen item and the user's wardrobe, ask the LLM for 1–2 concrete outfit ideas that pair the item with owned pieces.
- **Inputs:**
  - `new_item` (`dict`) — a listing dict (typically the top `search_listings` result).
  - `wardrobe` (`dict`) — wardrobe dict with an `"items"` list; may be empty.
- **Output:** `str` — a non-empty suggestion. With a populated wardrobe it names specific pieces; with an empty wardrobe it returns general styling advice instead of failing.

### Tool 3 — `create_fit_card`

- **Purpose:** Turn the outfit into a short, shareable OOTD-style social caption that mentions the item name, price, and platform once each.
- **Inputs:**
  - `outfit` (`str`) — the suggestion string from `suggest_outfit`.
  - `new_item` (`dict`) — the listing dict being showcased.
- **Output:** `str` — a 2–4 sentence caption. If `outfit` is empty/whitespace it returns a descriptive fallback message rather than raising or calling the LLM.

---

## Planning Loop

`run_agent(query, wardrobe)` in `agent.py` runs the loop for one interaction. It is a deterministic, linear pipeline where each step only runs if the previous one produced usable output:

1. **Initialize** a session dict (`_new_session`) — the single source of truth for the run.
2. **Parse** the natural-language query into `description`, `size`, and `max_price` with `_parse_query` (regex, no LLM call — fast and deterministic). The leftover text becomes the search description.
3. **Search** via `search_listings`. If it returns `[]`, the loop *short-circuits*: it writes a helpful message to `session["error"]` and returns immediately — the downstream tools have nothing to style, so calling them would be pointless.
4. **Select** the top-scoring result as `session["selected_item"]`.
5. **Suggest** an outfit via `suggest_outfit`. (This tool self-handles an empty wardrobe by returning general advice, so the loop never dead-ends here.)
6. **Create** the fit card via `create_fit_card`.
7. **Return** the completed session.

The loop "knows it's done" when it either returns a finished session (fit card produced) or short-circuits with an error after the search returns nothing. The decision at each step is driven entirely by the previous tool's return value stored in the session.

---

## State Management

All state for a single interaction lives in one `session` dict created by `_new_session(query, wardrobe)`. Rather than threading return values through function arguments, each step **writes its output back into the session** and the next step **reads from it**:

| Field | Written by | Read by |
|-------|-----------|---------|
| `query` | `_new_session` | `_parse_query` (step 2) |
| `parsed` | step 2 | step 3 (search args) |
| `wardrobe` | `_new_session` | step 5 (`suggest_outfit`) |
| `search_results` | step 3 | step 4 (select) |
| `selected_item` | step 4 | steps 5 & 6 |
| `outfit_suggestion` | step 5 | step 6 |
| `fit_card` | step 6 | returned to caller |
| `error` | any step that fails | caller / `app.py` |

This keeps tool calls decoupled (each tool takes plain values, not the session) while giving the caller a single object to inspect. `app.py`'s `handle_query` checks `session["error"]` first and only formats `selected_item` / `outfit_suggestion` / `fit_card` when the run succeeded.

---

## Interaction Walkthrough

**User query:** `"looking for a vintage graphic tee under $30"` (example wardrobe selected)

**Step 0 — Parse (`_parse_query`):**
- Output: `{"description": "looking for a vintage graphic tee", "size": None, "max_price": 30.0}`
- Why: extract structured search args without spending an LLM call.

**Step 1 — `search_listings`:**
- Input: `description="looking for a vintage graphic tee"`, `size=None`, `max_price=30.0`
- Why this tool: we have a description, so we look for matching listings first.
- Output: a ranked list; top result is **"Y2K Baby Tee – Butterfly Print"** ($18, depop).

**Step 2 — `suggest_outfit`:**
- Input: the Y2K Baby Tee dict + the example wardrobe.
- Why this tool: a valid item exists, so pair it with what the user owns.
- Output (real run): *"1. Pair the Y2K Baby Tee with the Baggy straight-leg jeans and Chunky white sneakers… 2. Combine it with the Wide-leg khaki trousers and Black combat boots…"*

**Step 3 — `create_fit_card`:**
- Input: the outfit string above + the Y2K Baby Tee dict.
- Why this tool: a complete outfit exists, so produce the shareable summary.
- Output (real run): *"just scored the cutest Y2K Baby Tee Butterfly Print on depop for $18 and i'm obsessed! paired it with my fave baggy straight-leg jeans and chunky white sneakers for a laid-back vibe…"*

**Final output to user:** three panels — the formatted listing, the outfit idea, and the fit card caption.

---

## Error Handling and Fail Points

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No listing matches the keywords / size / price | Returns `[]`; the planning loop short-circuits, sets `session["error"]`, and skips the remaining tools |
| `suggest_outfit` | Wardrobe is empty (no items to pair with) | Does **not** fail — calls the LLM for general styling advice for the item on its own |
| `create_fit_card` | `outfit` is empty or whitespace-only | Returns a descriptive fallback message instead of calling the LLM or raising |

**Concrete examples from testing:**

- **`search_listings` no-results →** query `"designer ballgown size XXS under $5"` produced:
  `No listings matched "designer ballgown" (size XXS, under $5). Try loosening the size or price, or different keywords.`
  The loop returned early; `outfit_suggestion` and `fit_card` stayed `None`.
- **`suggest_outfit` empty wardrobe →** running with `get_empty_wardrobe()` on the Y2K Baby Tee returned general advice: *"…This top pairs well with high-waisted pants, skirts, or shorts… Try pairing it with some distressed denim jeans and sneakers…"* — no crash, no empty string.
- **`create_fit_card` empty outfit →** calling with `outfit=""` returned:
  `Sorry, I can't make a fit card without an outfit to describe. Want help putting one together or finding other pieces first?`

---

## Spec Reflection

**One way planning.md helped during implementation:**
The Architecture diagram's explicit `[ERROR]` terminals made the short-circuit logic obvious before I wrote any code. Because I'd already decided that an empty `search_listings` result should return early rather than feed empty input to `suggest_outfit`, the `run_agent` loop translated almost line-for-line from the diagram — every branch label (`results = []`, `outfit = None`) became a guard clause. The state table I sketched in planning also told me exactly which session fields each step needed.

**One divergence from your spec, and why:**
My spec implied `suggest_outfit` would "return nothing" on an empty wardrobe and the loop would stop and tell the user to wear the item alone. In implementation I moved that handling *inside* the tool: `suggest_outfit` now always returns a non-empty string (general styling advice for an empty wardrobe) rather than `None`. This is simpler and more useful — the loop no longer needs a special branch for it, and a brand-new user with no wardrobe still gets a fit card instead of a dead end.

---

## AI Usage

I used Claude (in Claude Code) for two specific parts of the implementation:

**1. Implementing `run_agent` and the query parser.**
- *Input I gave it:* the `run_agent` TODO steps and docstring in `agent.py`, plus the **Planning Loop** and **Architecture** (ASCII diagram) sections of `planning.md`.
- *What it produced:* the full linear loop writing each result back into the session, including the early-return on empty search results, plus a new `_parse_query` helper using regex to pull `description` / `size` / `max_price` out of the natural-language query.
- *What I changed/overrode:* its first parser had two bugs I caught by testing it in isolation — it read the `30` in `"$30"` as a *size*, and grabbed the `28` inside `"W28"` as a *price*. I reordered parsing (size-phrase first, then price, then standalone size token) and tightened the price regex to require an explicit marker (`under`/`below`/`$`/…) so a bare size number can't be mistaken for a price.

**2. Wiring `handle_query` in `app.py`.**
- *Input I gave it:* my partially-written `handle_query` (which had bugs — `.trim()` instead of `.strip()`, and an unfinished `if query_dict` line) and the function's TODO steps.
- *What it produced:* the completed handler — empty-query guard, wardrobe selection from the radio choice, the `run_agent` call, the `session["error"]` check returning the message in panel 1, and a `_format_listing` helper that turns the selected listing dict into a readable multi-line panel string.
- *What I changed/overrode:* I had it add the dedicated `_format_listing` helper rather than inlining string-building in the handler, so the listing panel formatting stays readable and testable on its own.

---

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.
