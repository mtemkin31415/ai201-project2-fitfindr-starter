# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

Searches through the listings present in listings.json and returns a list of top matching items of clothing. The function will find the top matches by comparing item descriptions the item's size and max price.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): This represents a description of the item. The description can include the material, colors, use, fit and any extra details
- `size` (str): The size of the item of clothing (S/M/LG/XL - One Size - W28 - US8.5)
- `max_price` (float): The price in USD which the item should not exceed

**What it returns:**
Returns a list of item listings from listings.json that best match the input.
<!-- Describe the return value — what fields does a result contain? -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
If it fails or returns nothing, the LLM should say so and stop responsing. If there is no item of clothing the next tools will not be useful.

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
This function will suggest an outfit that makes sense based off of the item descriptions of the new_item and the items available in the users' wardrobe.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): The clothing item that best matches the user' suggestion
- `wardrobe` (dict): ... The users' wardrobe

**What it returns:**
<!-- Describe the return value -->
This returns [2-4] items that would work well together in an outfit based off their item descriptions

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
if this returns nothing the LLM should stop here and only sugggest wearing the item passed to it.

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Creates a short description of the new_item and describes the users' outfit in a way that can easily be posted to social media

**Input parameters:**
<!-- List each paramater, its type, and what it represents -->
- `outfit` (str): The users' suggested outfit     
- `new_item` (dict): The new item that the user wants to showcase

**What it returns:**
<!-- Describe the return value -->
A short description that is akin to a social media quote which describes the unique factors of the outfit and a short description of the new item

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
The LLM should say a fit_card can not be produced and ask the user if it needs help finding any other clothing items

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->\\

The user inputs a query that describes the item of clothing they are looking for, as well as any clothing pieces they already have (their wardrobe). The planning loop then decides which tool to call next based on what data it has so far and what each previous tool returned.

**Step-by-step logic:**

1. **Look at the user's input first.** The loop checks whether the user gave a description, size, and/or max price for an item they want.
   - If they did, it calls `search_listings(description, size, max_price)` to find the best matching item.
   - If the user *doesn't* know what they want (no item description) but listed wardrobe items, the loop skips searching and goes straight to suggesting an outfit from what they already own.

2. **Check what `search_listings()` returned.**
   - If it returned no matches, the loop stops and tells the user no listings were found — the remaining tools have nothing to work with, so there is no point continuing.
   - If it returned one or more matches, the loop picks the top match as `new_item` and moves on.

3. **Decide whether to suggest an outfit.** Once a `new_item` exists (either from the search or one the user already has), the loop calls `suggest_outfit(new_item, wardrobe)`.
   - If the wardrobe is empty or no sensible outfit can be built, `suggest_outfit()` returns nothing and the loop stops here, telling the user to simply wear the `new_item` on its own.
   - Otherwise it stores the returned outfit (2–4 items) and continues.

4. **Optionally create a fit card.** If a complete outfit exists, the loop calls `create_fit_card(outfit, new_item)` to produce the shareable, social-media-style summary.
   - If the outfit data is incomplete, the loop reports that a fit card can't be produced and asks the user whether they'd like help finding any other clothing items.

**How it knows it's done:**
The loop terminates when one of these is true: (a) a fit card has been successfully generated, (b) an outfit was suggested but no fit card was requested/possible, or (c) an earlier tool failed (no listings found or empty wardrobe) and there is nothing left to do. At each step the loop only advances if the previous tool produced usable output; any failure short-circuits the loop and returns a helpful message to the user instead of calling the next tool with empty data.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | | Ask if user wants to make an outfit out of closet without a new item
| suggest_outfit | Wardrobe is empty | | Return without picking an outfit
| create_fit_card | Outfit input is missing or incomplete | | If incomplete, fill in partial outfit. If missing return nothing

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     Use ASCII art or a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html).
     Do NOT embed an image — graders need to read your diagram directly in the file;
     an embedded image or screenshot cannot be evaluated.
     You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

```
  User query: { description, size, max_price, wardrobe }
      │
      ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                            PLANNING LOOP                                  │
  │   (decides the next tool from session state + each tool's return value)   │
  └─────────────────────────────────────────────────────────────────────────┘
      │
      │  has description/size/price?
      ├─► search_listings(description, size, max_price)
      │       │
      │       │  results = []                                 ┌─────────────────┐
      │       ├────────────────────────────────────────────► │ [ERROR] "No      │
      │       │                                               │ listings found"  │
      │       │  results = [item, ...]                        │  → return        │
      │       ▼                                               └─────────────────┘
      │   ┌───────────────────────────────────────────┐               ▲
      │   │ SESSION: selected_item = results[0]        │               │
      │   └───────────────────────────────────────────┘               │
      │       │ selected_item                                          │
      │       ▼                                                        │
      ├─► suggest_outfit(selected_item, wardrobe)                      │
      │       │                                                        │
      │       │  outfit = None  (wardrobe empty / no match)  ┌─────────┴───────┐
      │       ├────────────────────────────────────────────►│ [ERROR] "Wear    │
      │       │                                              │ item on its own" │
      │       │  outfit = [2–4 items]                        │  → return        │
      │       ▼                                              └─────────────────┘
      │   ┌───────────────────────────────────────────┐               ▲
      │   │ SESSION: outfit_suggestion = "..."         │               │
      │   └───────────────────────────────────────────┘               │
      │       │ outfit_suggestion + selected_item                      │
      │       ▼                                                        │
      └─► create_fit_card(outfit_suggestion, selected_item)            │
              │                                                        │
              │  outfit data incomplete                     ┌──────────┴──────┐
              ├────────────────────────────────────────────►│ [ERROR] "Can't   │
              │                                              │ make fit card —  │
              │  fit_card = "..."                            │ need more items?"│
              ▼                                              │  → return        │
          ┌───────────────────────────────────────────┐     └─────────────────┘
          │ SESSION: fit_card = "..."                  │
          └───────────────────────────────────────────┘
              │
              ▼
          Return session { selected_item, outfit_suggestion, fit_card }
```

**Legend**
- **Solid boxes** = components: the planning loop, session state writes, and error terminals.
- **`├─►` arrows** = a tool call; the label after the arrow names the data passed in.
- **Branch labels** (`results = []`, `outfit = None`, etc.) = the return value the loop inspects to decide what happens next.
- **Error path:** each tool has its own `[ERROR]` terminal on the right. When a tool returns empty/incomplete data, the loop short-circuits to that terminal, returns a helpful message, and never calls the next tool with empty input.

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

**Milestone 4 — Planning loop and state management:**

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

Full user interaction: A full user interaction might look like: 
1. User enters query to LLM about what they are looking for (type, desc, price range, etc) and what they are wearing/in their closet (optional).
2. AI model runs search_listings() with the parameters the user passes in. The model then attempts to find the best match.
3. LLM suggests a fit using suggest_outift() and returns a fit that would work with the suggested piece of clothing
4. A fit card can also be generated by the LLM for a concise summary of the interaction via get_fit_card()

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->

**Step 3:**
<!-- Continue until the full interaction is complete -->

**Final output to user:**
<!-- What does the user actually see at the end? -->
