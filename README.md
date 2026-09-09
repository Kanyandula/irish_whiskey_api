# Irish Whiskey API

A read-only JSON API for an Irish whiskey knowledge app: the four whiskey
types, the distilleries that make them, the brands, individual expressions with
tasting facts, editorial articles, and a news feed.

Runs on [`json-server`](https://github.com/typicode/json-server) against a
generated `db.json`. It is a **development mock**, but the endpoint contract
below is frozen and will be reimplemented as-is by a real backend later.

## Quick start

```bash
npm install
npm run json:server     # http://localhost:3001
```

Images are served statically from `./public`, e.g.
`http://localhost:3001/images/whiskeys/redbreast-12-year-old.jpg`.

## Contract

**This contract is frozen.** The client codes against exactly this surface —
nothing more. Anything outside it is a migration hazard (see
[Migration rules](#migration-rules)).

```
GET /whiskeys?_page={n}&_limit=20&_sort=rating&_order=desc
GET /whiskeys?type_id={slug}
GET /whiskeys?brand_id={slug}
GET /whiskeys?distillery_id={slug}
GET /whiskeys?id={slug}&id={slug}       # related cards; repeated param = OR
GET /whiskeys?name_like={query}         # search
GET /whiskeys/{slug}

GET /distilleries        GET /distilleries/{slug}
GET /brands              GET /brands/{slug}
GET /types               GET /types/{slug}
GET /articles            GET /articles/{slug}
GET /news?_page={n}&_limit=20&_sort=published&_order=desc
```

Paging applies to `/whiskeys` and `/news` only. Every other collection is under
50 rows — fetch it whole.

Responses are **bare JSON arrays** for collections and a **bare object** for a
single resource. There is no envelope. A missing resource is a `404` with no
meaningful body.

## Resources

### `whiskeys`

```json
{
  "id": "redbreast-12-year-old",
  "name": "Redbreast 12-Year-Old Single Pot Still",
  "type_id": "single-pot-still",
  "brand_id": "redbreast",
  "brand_name": "Redbreast",
  "distillery_id": "midleton",
  "distillery_name": "Midleton Distillery",
  "abv": 40.0,
  "age_years": 12,
  "price_usd": 64.0,
  "rating": 94,
  "tasting_note": "Rich sherried fruit and spice",
  "excerpt": "First ~200 characters of the source review.",
  "image_url": "http://localhost:3001/images/whiskeys/redbreast-12-year-old.jpg",
  "related_whiskey_ids": ["green-spot", "powers-johns-lane-12"],
  "source_url": "https://vinepair.com/review/...",
  "source_publisher": "VinePair",
  "source_author": "Tim McKirdy",
  "source_published": "2023-03-13"
}
```

| Field | Type | Notes |
|---|---|---|
| `id` | string | slug, stable across rebuilds |
| `type_id` | string | FK → `types` |
| `brand_id` | string | FK → `brands` |
| `brand_name` | string | denormalized for the detail header |
| `distillery_id` | string \| null | FK → `distilleries`; **null for sourced brands** |
| `distillery_name` | string \| null | denormalized; null when `distillery_id` is |
| `abv` | number | percent, e.g. `46.0` |
| `age_years` | number \| null | null when there is no age statement |
| `price_usd` | number \| null | USD; source reviews are US-published |
| `rating` | number | 0–100 |
| `related_whiskey_ids` | string[] | slugs, may be empty |

`brand_name` and `distillery_name` are duplicated **deliberately** so the detail
screen renders its header in one request. That is the only denormalization —
never add more fields from the related resource.

**`distillery_id` is nullable and often null.** Many Irish whiskey brands do not
distil: independent bottlers and sourced brands (High N' Wicked, Ha'penny, Lost
Irish, Egan's, Knappogue Castle, Grace O'Malley, Limavady, Michael Collins) buy
mature stock. Clients must handle a whiskey with no distillery.

### `distilleries`

```json
{
  "id": "bushmills",
  "name": "Bushmills Distillery",
  "county": "Antrim",
  "country": "Northern Ireland",
  "lat": 55.2069, "lng": -6.5197,
  "founded": 1784,
  "website": "https://www.bushmills.com",
  "visitor_centre": true,
  "description": "...",
  "image_url": "..."
}
```

`country` is `"Ireland"` or `"Northern Ireland"` — both are Irish whiskey under
the GI. `lat`/`lng` are flat rather than nested so the client can build a
`LatLng` directly.

### `brands`

```json
{ "id": "redbreast", "name": "Redbreast", "distillery_id": "midleton",
  "description": "...", "image_url": "..." }
```

`distillery_id` is nullable here for the same reason as above.

### `types`

The four categories defined by EU Regulation 2019/787 and the Irish Whiskey
Technical File.

```json
{ "id": "single-pot-still", "name": "Single Pot Still Irish Whiskey",
  "short_name": "Single Pot Still", "description": "...",
  "legal_definition": "...", "image_url": "..." }
```

### `articles`

Owned editorial content — what Irish whiskey is, and its history. Body is
markdown.

```json
{ "id": "what-is-irish-whiskey", "title": "...", "summary": "...",
  "body": "## ...", "image_url": "...", "updated": "2026-01-15" }
```

### `news`

Headline, link and short excerpt only, from publisher RSS feeds. Full article
text is never stored — the client links out.

```json
{ "id": "2026-01-12-whiskeywash-midleton-release", "title": "...",
  "summary": "...", "url": "...", "source": "The Whiskey Wash",
  "published": "2026-01-12", "image_url": null }
```

## Migration rules

`json-server` offers conveniences that a real backend would have to
hand-reimplement. The contract above deliberately avoids them so the client
survives the migration untouched.

**Do not use:**

- **`_embed` / `_expand`** — they invent nested response shapes that become
  bespoke per-endpoint DTOs on a real backend. The denormalized `brand_name` /
  `distillery_name` fields exist so you never need them.
- **`?q=`** — full-text across *every field of every object*, including
  `excerpt`. A SQL `ILIKE`/`tsvector` equivalent returns a different result set
  with different ranking, so a search screen built on `q` visibly breaks at
  migration. Use `?name_like=`, which maps cleanly to `WHERE name ILIKE '%x%'`.
- **`X-Total-Count` / `Link` response headers** — paginate until
  `response.size < limit` instead.
- **`_gte` / `_lte` / `_ne` / `_start` / `_end`, nested `?a.b=`, multi-field
  `_sort=a,b`** — all work today, none have a screen behind them, all cost work
  later.
- **`POST` / `PUT` / `PATCH` / `DELETE`** — `json-server` exposes full CRUD by
  default and writes to `db.json`. This API is read-only; writes would mean
  building auth.

Everything in the contract reduces to `WHERE` / `ORDER BY` / `LIMIT`.

## Rebuilding `db.json`

`db.json` is **generated — do not hand-edit it.** The source of truth is the
CSV and markdown under `tools/source/`.

```bash
python3 tools/build_db.py
```

The script normalizes types (`"56.70%"` → `56.7`, `"$500.00"` → `500.0`),
slugifies ids, resolves related whiskeys by title, decodes HTML entities, and
asserts referential integrity before writing. It fails loudly rather than
emitting a broken file.

To correct data, edit the CSV and re-run.

## Data sources and attribution

- **Whiskey facts** (ABV, price, age, category, rating) and review excerpts:
  [VinePair](https://vinepair.com), reviews by Tim McKirdy. Each record carries
  `source_url`, `source_publisher` and `source_author`, and clients link out for
  the full review. Only facts and a short attributed excerpt are stored — never
  the full review text.
- **Distillery coordinates**: [Oralytics Irish Whiskey Distilleries data
  set](https://oralytics.com/data-sets/irish-whiskey-distilleries/).
- **Whiskey type definitions**: EU Regulation 2019/787 and the Irish Whiskey
  Technical File.
- **News**: publisher RSS (The Whiskey Wash, Whisky Advocate, VinePair) —
  headline, link and excerpt only.
- **Articles**: written for this project.

## A note on `npm audit`

`npm audit` reports vulnerabilities in `json-server@0.17.3`'s transitive
dependencies. They are ReDoS/DoS issues in a **localhost development mock with
no untrusted input**, and are not worth acting on here.

`json-server@1.x` is a rewrite that drops `_embed`/`_expand`/`q` and changes the
paging parameters, so `npm audit fix --force` would break the contract above.
The version is pinned deliberately.
