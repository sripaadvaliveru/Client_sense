# ClientSense

**A memory-powered agent that remembers how your clients actually behave.**

You tell it "Northwind asked for a 6th round of revisions." It tells you
Northwind has a *documented history* of 4–5 rounds, pays 8–31 days late while
apologising, and frames large requests as small ones — then tells you what to
write into the contract this time.

The point is not that a language model can summarise a paragraph. The point is
that **it remembers across engagements**. Interaction 1 gets you "not enough
history." Interaction 7 gets you a specific, evidence-cited pattern with a
number attached.

---

## Table of contents

- [Why this exists](#why-this-exists)
- [Quick start](#quick-start)
- [How Hindsight is used](#how-hindsight-is-used) ← *the core of this project*
- [The learning curve](#the-learning-curve) ← *real output*
- [The three flows](#the-three-flows)
- [API reference](#api-reference)
- [Design decisions and trade-offs](#design-decisions-and-trade-offs)
- [Project structure](#project-structure)
- [Testing](#testing)
- [Known limitations](#known-limitations)

---

## Why this exists

Every freelancer re-learns their clients from scratch. You finish a project,
six months pass, and the next one starts with you remembering "hmm, this
person was a bit difficult about revisions" without being able to say how
difficult, how often, or what it cost you.

CRM tools don't solve this. They store what you typed; nobody writes down that
a client paid late four times in a row, or that they always describe a scope
increase as "a quick addition." That knowledge lives in people's heads and
leaves when they do.

ClientSense makes that knowledge explicit, and then does something with it:
brief you before an engagement, and interrupt you during one.

**Is this a real business problem?** Yes. Freelancer admin tooling is a real
market, and retainer/prepayment enforcement is a genuine pain point —
independent workers routinely lose money to late payment because they have no
institutional memory to fall back on.

---

## Quick start

### Prerequisites

- Python 3.11+
- A [Hindsight Cloud](https://ui.hindsight.vectorize.io) account
  (promo code `MEMHACK99` gives $50 in credits)
- A browser. **No Node.js, no build step, no bundler.**

> **You do not need an LLM API key.** Hindsight runs both fact extraction and
> reasoning server-side with its own configured provider. ClientSense never
> calls a model directly.

### 1. Configure

```powershell
cd backend
pip install -r requirements.txt
copy .env.example .env
```

Edit `backend/.env` and paste your key:

```ini
HINDSIGHT_API_KEY="hsk_..."
HINDSIGHT_BANK_ID="clientsense"
```

The bank is created automatically on its first write, so there is nothing to
provision up front.

### 2. Seed and provision

```powershell
cd ..
python scripts/seed_data.py      # 33 interactions across 3 clients
python scripts/setup_bank.py     # mission, disposition, directives
```

Both are safe to re-run: seeding replaces each client's history via a stable
`document_id`, and provisioning skips directives that already exist.

### 3. Run

**Terminal 1** — API:
```powershell
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2** — frontend:
```powershell
python -m http.server 5500 --directory frontend
```

Open **http://127.0.0.1:5500**

Check it's healthy:
```powershell
curl.exe http://127.0.0.1:8000/health
```

---

## How Hindsight is used

This is the part worth reading. ClientSense is a thin shell over three
Hindsight operations — it holds no state of its own, and the entire value of
the product lives in what has been retained.

### `retain()` — writing

Raw interaction text goes in; Hindsight's LLM extracts atomic facts and
consolidates recurring observations. One retained interaction typically becomes
several memories.

The seeded 33 interactions expand to **74 memories**, because "Client paid
$1,500 on 2026-06-24" and "Client is punctual" are different facts.

Every retain stamps `tags: ["client:<slug>"]`.

### `recall()` — reading

Briefs and nudges are scoped with `tags` + `tags_match="all_strict"`, so a
query for one client can never surface another's history.

### `reflect()` — reasoning

`reflect()` is called with a `response_schema`, so it returns
`structured_output` — typed JSON — rather than prose to be scraped. With
`include_facts=True` it also returns `based_on`: the exact memories it cited.

So a brief is an object with a `red_flags[].evidence_count`, not a paragraph
we happened to regex.

### Bank-level policy

`scripts/setup_bank.py` applies configuration to the bank itself, so the rules
bind every call rather than living in a prompt someone could delete:

| Setting | Value | Why |
|---|---|---|
| `retain_mission` | Extract behavioural facts: payment lateness, revision counts, scope shifts — always carrying through dates, amounts and day counts | Governs what gets stored |
| `reflect_mission` | Advisor to a freelancer; an honest "not enough history" beats a confident guess | Governs how it reasons |
| `disposition_skepticism` | `4` (scale 1–5, 3 = balanced) | Discourages agreeable fabrication |
| Directive: *Two instance threshold* | Flag a risk only when ≥2 separate interactions support it | Enforced on every reflect |
| Directive: *Nudge discipline* | Default to silence; never nudge on a routine interaction | Prevents alert fatigue |
| Directive: *Cite evidence* | Always cite dates, counts, quotes | Makes briefs checkable |
| Directive: *No fabrication* | Never assert a pattern not backed by retained memory | — |

You can see the two-instance threshold working in the learning curve below: the
first red flag does not appear until step 4, when the second confirming
interaction lands.

### The proactive nudge

After every logged interaction, `reflect()` re-asks: *does this touch a
pattern this client's history has established, and would the freelancer act
differently if they knew?*

It classifies the match as one of:

- **`new_escalation`** — this goes beyond the client's own normal
- **`known_pattern`** — this repeats established behaviour
- **`none`** — stay silent

Both escalation *and* known-pattern flag, because a known-costly pattern still
deserves surfacing at the moment you're deciding whether to absorb another
round for free. Routine interactions return `none`.

---

## The learning curve

This is real output. Not a mock, not an illustration — a script that retains
one interaction, then re-asks the same question, seven times.

```powershell
python scripts/memory_showcase.py "Northwind Collective"
```

Same client. Same question. Only the memory changes.

**After 1 interaction** — confidence `low`, 0 flags:
> The record is limited; the client paid their 30% deposit for a 6-page
> marketing site on June 1, 2026, the same day it was requested. **There is
> not enough history to establish a long-term pattern.**

**After 4 interactions** — the first flag appears, exactly when the second
instance lands:
> `[medium] Delayed milestone payments due to internal accounting backlogs. (n=2)`

**After 7 interactions** — confidence `high`, 2 flags:
> **Payments:** The client exhibits a pattern of late payments attributed to
> an internal accounting backlog. Milestone 1 due July 2, 2026, was received
> 8 days late on July 10, 2026…
>
> **Scope:** The client **shifted from** efficient, consolidated feedback in
> June 2026 **to** recurring scope creep. They frequently downplay additional
> work as "quick additions" or "small tweaks"…
>
> `[high] Persistent Payment Delays (2 instances)`
> `[medium] Repeated Scope Creep (2 instances)`

| | Interaction 1 | Interaction 7 |
|---|---|---|
| Memories stored | 1 | 11 |
| Confidence | `low` | `high` |
| Red flags | 0 | 2 |
| Memories cited | 2 | 12 |
| Scope reading | *"not enough history to describe their revision or scope management process"* | *"shifted from efficient to recurring scope creep"* |
| Advice | *"confirm scope changes in writing"* | *"require a signed change order and upfront payment for any work deviating from the initial brief"* |

Two things worth noticing:

1. **Nothing in interaction 1 pointed at this.** One polite late payment is
   noise. The pattern only exists in the accumulation — which is the argument
   for a memory layer over a longer context window.
2. **The last brief detects a trajectory, not a static trait.** "Shifted from
   X to Y" is a claim about *change over time* that requires history to make.
   The recommended contract clause changes accordingly.

---

## The three flows

**1. Log an interaction** — freeform text plus optional event type, amount and
project. Calls `retain()`, then immediately runs the nudge check. The two are
decoupled: if the nudge call fails, your interaction is still saved.

**2. Brief me** — returns payment behaviour, revision/scope behaviour,
communication style, red flags with evidence counts, a concrete
recommendation, a confidence level, and the list of memories it cited.

**3. Timeline** — the client's memories in chronological order, so you can
check the brief rather than trusting it.

---

## API reference

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Service metadata |
| `GET` | `/health` | App health **including real Hindsight reachability** |
| `GET` | `/clients` | Every client with retained memory, with counts |
| `GET` | `/timeline/{client_name}` | Chronological memory inventory |
| `POST` | `/client-brief` | Structured brief (`{client_name}`) |
| `POST` | `/log-interaction` | Retain, then nudge (`{client_name, interaction_text, ...}`) |
| `POST` | `/check-nudge` | Nudge decision without saving |

Interactive docs at http://127.0.0.1:8000/docs

---

## Design decisions and trade-offs

**Per-client isolation uses tags, not metadata filters.**
The recall API has no `metadata_filter`. Tags with `all_strict` are the
supported primitive — and this is not theoretical. Metadata is *not* reliably
propagated to every fact Hindsight extracts: a first implementation stamped
metadata on retain and filtered on it, and the brief came back "no history
available" for every client. Tags are the only thing that reliably scopes.

**Structured output instead of parsing prose.**
Briefs are schema-constrained. This is the difference between "red_flags with
an evidence count of 4" and a regex hoping to find the word "risk". It also
means the frontend never displays a fabricated number.

**When there's no evidence, say so.**
A client with no history gets a brief that says so, with `confidence: low`,
rather than a plausible-sounding paragraph. The bank disposition and the *No
fabrication* directive both push on this.

**A nudge failure must never lose data.**
`/log-interaction` retains first, in its own try block. The nudge is best
effort.

**The nudge defaults to silence.**
An agent that cries wolf gets ignored, which is worse than one that never
warns. The *Nudge discipline* directive is a bank-level rule, not a prompt
nicety.

**No LLM key in the app.**
Hindsight handles inference. A second LLM integration would duplicate
capability and add a failure mode for no benefit.

---

## Project structure

```
client-sense/
├── backend/
│   ├── app/
│   │   ├── config.py             # settings, absolute .env resolution
│   │   ├── hindsight_client.py   # the entire memory layer
│   │   └── main.py               # FastAPI routes
│   ├── scripts/
│   │   ├── diagnose.py           # inspect raw bank contents
│   │   └── smoke_test.py         # live brief + nudge check
│   ├── tests/test_api.py         # 19 tests, memory layer mocked
│   ├── .env.example
│   ├── pytest.ini
│   └── requirements.txt
├── frontend/
│   ├── index.html                # 3 views
│   ├── css/style.css
│   └── js/app.js                 # all UI logic
├── scripts/
│   ├── memory_showcase.py        # the learning-curve demo
│   ├── seed_data.py              # synthetic data
│   └── setup_bank.py             # mission, disposition, directives
├── .gitignore
├── LICENSE
└── README.md
```

---

## Testing

```powershell
cd backend
python -m pytest -q          # 19 passed
```

The memory layer is mocked throughout, so the suite is fast, offline, and
spends no tokens. Beyond route and validation tests it pins the things that
previously broke silently:

- client slugs are stable and URL-safe
- the brief and nudge schemas are valid, and `should_nudge` is a real boolean
  rather than a keyword match
- a client with no history gets an empty brief, not an invented one
- whitespace-only input is rejected (`min_length` alone lets `"   "` through)
- a nudge failure does not lose an already-retained interaction
- upstream failures surface as 502, missing credentials as 503

Live checks against the real bank:

```powershell
python scripts/smoke_test.py    # real brief + real nudge
python scripts/diagnose.py      # memory counts, tags, metadata
```

---

## Known limitations

Stated plainly, because a reviewer will find these anyway.

- **Synthetic data.** Three seeded clients and one showcase client, all
  fictional. The learning curve is real; the *clients* are invented.
- **Intermediate briefs contain occasional misreadings.** One mid-run
  interpretation of a payment date was wrong. The first and final readings,
  which are the ones the showcase quotes, are correct. A tool that reasons
  over compressed summaries inherits their errors.
- **The cited-memories list is returned by the API but not yet rendered in
  the UI.** The Evidence card shows the count; the underlying list is there in
  `based_on`.
- **Client names round-trip through a slug**, so "Bloom & Co Boutique" is
  displayed as "Bloom Co Boutique". The slug is stable, but a name with
  unusual punctuation could in principle collide.
- **Single-user.** No auth. This is one freelancer's memory bank.

---

## License

MIT — see [LICENSE](LICENSE).
