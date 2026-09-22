# Naming candidates — replacing "gavel"

*Working document · 22 September 2026 · research complete, decision open*

Screening for a new product name. The product is unchanged: an AI meeting chair that
refuses to let a meeting be booked without an agenda, joins the call as a participant, and
enforces the agenda live. Category claimed: **time governance**, explicitly not meeting
notes. Persona: **Karen**. Buyer: **enterprise**. Near-term audience: **investors**.

---

## 0 · What I actually checked, and what I could not

**Read this before trusting any "available" below.** The confidence levels are not decorative.

| Check | Method | Confidence |
|---|---|---|
| Existing companies / products | Web search, then fetched the live homepage of every domain that resolved | **Good.** Finds anything with a web presence. Will miss stealth companies and unlaunched brands. |
| Domain registration | `dig NS` sweep across all candidates, then `whois` on the interesting ones | **High.** `whois` "Domain not found" is authoritative. NS present = registered, full stop. |
| Domain *in use* vs *parked* | `curl` the homepage, read the `<title>` and stripped text | **High**, and it changed three verdicts. Afternic/Sedo/Efty nameservers = listed for sale, not an operating company. |
| npm / PyPI | `registry.npmjs.org/<name>`, `pypi.org/pypi/<name>/json`, validated against a nonsense control that correctly returned 404 | **High.** |
| GitHub org name | `github.com/<name>` HTTP status, same control | **Medium.** Tells me the handle is taken, not by whom or whether it is active. |
| **Trademark** | **Failed.** `tmsearch.uspto.gov` API rejects unauthenticated queries; `developer.uspto.gov` 301s away; EUIPO eSearch is a JS app that returns a shell; Justia returns **403** to automated fetches. | **LOW — see below.** |

### The trademark caveat, stated plainly

**I did not perform a trademark registry search.** I could not reach USPTO, EUIPO or TMview
programmatically. Everything below labelled "trademark" comes from **web-search proxies**
(indexed Justia pages, uspto.report mirrors) and is therefore:

- incomplete — it surfaces what a search engine happened to index, not the register;
- possibly stale — Justia mirrors lag the USPTO;
- **silent on Nice classes 9 and 42**, which are the only two classes that matter for us,
  and on class 38 which can also conflict.

**No name here is cleared.** Before committing, the shortlisted name needs a paid clearance
search (Class 9 + 42 + 38, US and EU) from a trademark attorney. That is a few hundred
dollars and it is the cheapest insurance on this entire decision — this is the second
rename, and a third would be worse than either.

I also distinguish two different failure modes throughout, because they are not the same problem:

- **Legally blocking** — a live mark in class 9/42 that would stop registration. Unverified for everything.
- **Practically crowded** — the name is already the first Google result for someone else. A
  band, a fencing company or a PR agency does not block registration but does wreck criterion 1,
  and an investor googling us hits it on day one.

---

## 1 · Why we are renaming — "gavel" verified

**Confirmed, and worse than "a startup has the name."**

**Gavel** (`gavel.io`) is a legal-AI company founded 2020 by Dorna Moini, a former Sidley
Austin associate; previously **Documate** ("Documate is now Gavel!"), itself preceded by
HelpSelf Legal (2018). Los Angeles. Products: **Gavel Workflows** (legal document
automation) and **Gavel Exec** (AI contract review inside Microsoft Word, launched 2025,
extended to the web in April 2026). Backers include Neo Ventures, Fuel Capital, Resolute
Ventures and Precursor Ventures. Pricing runs $83–$417/mo (Workflows) and from $160/mo per
user (Exec).

**It has been acquired by Relativity**, a legal-data-intelligence company that filed a draft
S-1 with the SEC in March. So the name is not merely taken by a startup — it is now attached
to a brand inside a company heading for an IPO, with the trademark budget that implies.

Independently, **`gavel.ai` is registered** and has been since 2018-10-24 (Namecheap, privacy
service, expires 2027-10-24) — so the `.ai` fallback was never available either.

Sources: [gavel.io/about](https://www.gavel.io/about) ·
[Global Legal Post on the Relativity acquisition](https://www.globallegalpost.com/news/legal-intelligence-firm-relativity-acquires-ai-document-automation-platform-gavel-1194169179) ·
[LawSites, April 2026](https://www.lawnext.com/2026/04/gavel-launches-web-based-ai-contract-platform-expanding-gavel-exec-beyond-its-word-add-in.html) ·
[PitchBook profile](https://pitchbook.com/profiles/company/343288-00)

### One lesson worth carrying into the new name

"Gavel" collided with a **legal**-AI company because a gavel is a *judicial* object. Judicial
vocabulary — writ, arbiter, bench, tribunal, curia, docket, praetor — is simultaneously the
most crowded trademark territory in AI right now and the exact neighbourhood we are trying to
leave. **Parliamentary and procedural vocabulary is the better seam:** it carries the same
authority-over-proceedings meaning, is about *conduct of a meeting* rather than *judgement of
a person*, and is far less contested. Every finalist below sits in that seam or in horology.

I also treated **descriptiveness as a scoring dimension, not a footnote.** A name that
literally describes the product — *Agendum*, *Timebox*, *Timekeeper*, *Floorclock* — risks
refusal at the USPTO as merely descriptive and, if granted, yields a mark too weak to defend.
For a rename billed as hard to reverse on an enterprise product, that is close to disqualifying.

---

## 2 · Top 5, ranked

### 1 · DECORUM

**What it means.** Propriety; correct and dignified conduct, especially in formal
proceedings. *"Order and decorum"* is the chair's own phrase — it appears verbatim in the
standing rules of legislatures and, as it happens, in the published meeting rules of ordinary
organisations ([Campbell County, WY: "Meeting Protocol and Rules of
Decorum"](https://www.campbellcountywy.gov/2052/Meeting-Protocol-and-Rules-of-Decorum)).

**First read.** Formal conduct in a professional setting — serious, institutional, zero joke
risk. (With one caveat: a competing "decor" reading is evidenced below, and it is the single
strongest argument against this name. Read both sections together.) It says *this meeting will be conducted properly* without saying anything about
software, which is what lets it become a brand rather than a description.

**The easter egg.** The word itself is faintly, deliciously prim — it is the vocabulary of
someone about to tell you that you have fallen short. That is Karen's exact register, and it
arrives as tone rather than as a joke. *"Decorum has joined the meeting"* reads straight to a
CFO and lands differently for anyone who has met her. Critically, nobody hearing it for the
first time thinks "Karen"; they think "conduct." The second layer stays second.

**Memorability.** Three syllables, stress on the second, a word every English speaker already
owns. Spells itself after one hearing. Travels well: *décorum* (FR, in active use),
*decoro* (ES/IT), *Dekorum* (DE) — no bad reading found in any major market.

**Availability.**
- *Companies:* The one real software holder is [decorum.work /
  decorumapp.com](https://decorum.work/) — B2B **order management and CRM for manufacturing**,
  founded 2017, India. Different category, no funding on record, zero reviews on G2 or
  SoftwareSuggest. Also a *Décorum* board game (Floodgate Games) with a companion app, and a
  "Decorum CRM" Android app.
- *Companies — one lead chased down, because it looked bad:* a search surfaced what appeared
  to be a second "Decorum," described as a **team-collaboration platform with team chat and
  video conferencing** — which would sit directly in our adjacency and would sink the name.
  **It does not appear to be a real product.** The claim traces to a single page on the
  aggregator `apibit.com`; I fetched that page directly and it describes **order management**,
  lists no vendor or company, has empty Features / Pricing / Screenshots sections, shows
  "0/5 (0 Reviews)" under a 5-star graphic, and its one outbound link is an affiliate-tagged
  redirect to `decorum.work` — the manufacturing-order product above. The chat-and-video prose
  reads as AI-generated SEO filler on a listing farm. No corporate homepage, pricing page or
  customer base exists for it anywhere. **Stated confidence: probably not real, not certainly
  not real.** I could not prove a negative, and it is recorded here rather than dropped.
- *Conclusion on incumbents:* **no verifiable AI, meetings or enterprise-collaboration company
  holds this name** — with the aggregator listing above as the one unresolved smudge on that
  claim.
- *Domains:* `decorum.com` — registered 1999, GoDaddy, nameservers `eftydns.com` → **listed
  for sale on the Efty marketplace**, returns a 301 with no site. Acquirable; price unknown.
  `decorum.ai` — registered 2022-04-07, GoDaddy/Domains By Proxy, expires 2028. **Fetched it:
  a stalled placeholder** reading *"decorum. Your vision. Our expertise. **Unveiling Summer
  2025**"*, served with an unrendered Django template tag (`{% block title %}`) leaking into
  the page title. Over a year past its own launch date and visibly broken — not an operating
  product.
- *Trademark (low confidence, proxy only):* Four DECORUM word marks surfaced on Justia
  mirrors — Reg. 1505286, 3422902, 3422900, 1891740 — and **all four are cancelled** under
  Section 8 (failure to file maintenance declarations), the most recent in 2020. Every one was
  in **home furnishings and retail** — classes 20 and 35, one of them owned by *Nostalgia
  Lighting, Inc.* One record (Reg. 1505286, filed 1987) shows **class 042**, which looks
  alarming until you note it is for *"retail store services in decorative bathroom fixtures"*:
  before the 2002 reclassification, class 42 was the catch-all miscellaneous-services class
  that retail sat in. It is not a software mark. *(Moderate confidence on that reclassification
  point — worth a lawyer confirming, not worth panicking over.)*
- *Trademark — the one live lead, resolved:* the newer application I flagged, **serial
  99536798**, is owned by *Decorum Lifestyle, LLC* and the mark is **"DECORUM LIFESTYLE"** —
  a two-word mark, not bare DECORUM. The 99-series serial means a very recent filing, so no
  third-party database has ingested the class or goods recitation yet and I could not retrieve
  it: `uspto.report` sits behind Cloudflare (403), Justia 403s automated fetches, and TSDR
  needs a browser. **"Lifestyle" points back to the same home/decor space as the four cancelled
  marks**, but that is inference, not evidence. **Anyone can settle this in thirty seconds** at
  [tsdr.uspto.gov](https://tsdr.uspto.gov/) with serial 99536798 — do it before signing off.
- **Nothing in class 9 or 42 surfaced for DECORUM** — but per §0, absence of evidence from a
  search engine is weak evidence of absence from a register.
- *Registries:* npm `decorum` taken — an abandoned JS decorator library, v0.1.0, last
  modified 2022-04-28. PyPI taken. `github.com/decorum` taken.

**Strongest argument against.** **The "decor" misread is real and commercially evidenced.**
Every single cancelled DECORUM mark was home furnishings; a stranger hearing the name cold may
route to interior design before formal conduct, and non-native speakers will see *decor* in the
first five letters. Secondly, the name describes *conduct*, not *time* — the pitch claims the
category "time governance," and Decorum does not say clock. Thirdly, `decorum.com` is a
for-sale parked asset of unknown price, so the clean domain story costs money that has not been
quoted. It is a good enterprise name that does slightly less semantic work for the specific
pitch than Cloture or Escapement do.

---

### 2 · CLOTURE

**What it means.** The parliamentary motion that **cuts off debate and forces the question**.
In the US Senate it is the procedure by which a body says *this has gone on long enough, we
are moving to the decision.* It is, almost uncannily, a one-word description of the product's
core behaviour.

**First read.** For anyone who follows legislative process: precise, formal, procedural. For
everyone else it reads as a clean, slightly unfamiliar, professional-sounding word — which is
exactly what a defensible trademark is made of.

**The easter egg.** Karen moving cloture on the person who called the meeting. It is the most
elegant version of the joke in this whole list, because the strictness is *in the procedure*
rather than in the persona — the word is impeccably polite and completely final.

**Memorability.** Two syllables, short, easy to say on stage.

**Availability — the best of any candidate here, by a distance.**
- *Companies:* **No technology company anywhere under this name.** The entire search result
  set is French and Québécois **fencing** businesses — Uni Clôtures Alpha, Côté Clôture,
  Clôtures Directes, Clôtures Oasis — because *clôture* is French for "fence."
- *Domains:* `cloture.ai` — **whois returns `Domain not found`. Unregistered.** That is a hard
  verdict from the registry, not an inference. `cloture.com` is registered (2000, WHC Online
  Solutions, Cloudflare NS) and I fetched it: a **French-language e-commerce site**
  (*"Cloture.com — Achetez en ligne"*), i.e. fencing, in use.
- *Registries:* **npm `cloture` free (404). PyPI `cloture` free (404).** Only
  `github.com/cloture` is taken. No candidate in this document is cleaner on code registries.
- *Trademark:* unverified (§0). But a namespace occupied only by regional fencing contractors
  in class 6/19 is about as favourable a starting position as exists for a class 9/42 filing.

**Strongest argument against.** **It fails criterion 2, the one criterion that is about the
name doing its job in a room.** The brief asks for "spellable after hearing it once," and a
large fraction of English speakers will write **"closure"** — a real, common, adjacent-meaning
word that is one letter and one sound away. Pronunciation splits too: *KLOH-cher* in American
usage, *klo-TYOOR* from anyone reading it as French. Every sales call and every conference
badge pays that tax forever. And the French problem is not cosmetic for a product selling into
European enterprise: to a French speaker the primary meaning is **fence**, the search results
are wall-to-wall fencing contractors, and `cloture.com` is itself a French fencing shop. The
saving grace — *clôture de la séance* is genuine French parliamentary vocabulary for closing a
session — is the *second* meaning, not the first. Finally, cloture is a distinctly **US-Senate**
concept; much of the European audience will not recognise it at all, so the elegance is lost on
them and only the spelling problem remains.

---

### 3 · ESCAPEMENT

**What it means.** The mechanism in a mechanical clock that releases the gear train **one
tooth at a time**. It is the specific part that converts stored energy into *rationed,
regular, non-negotiable* increments — without it the mainspring unwinds all at once and the
clock is useless. It is the single best physical metaphor available for what this product
does to a meeting: someone gets exactly their allotment, then the next tooth releases.

**First read.** Precision horology. Craft, mechanism, engineered exactness. Enterprise-safe,
faintly premium.

**The easter egg.** The mechanism is *indifferent*. It does not negotiate, it does not care
who you are, and it makes an audible click when your portion ends. Karen, rendered as
engineering.

**Memorability.** Three syllables, e-SCAPE-ment, built from a word everyone knows, so it
spells itself after one hearing.

**Availability.**
- *Companies:* **No funded startup, and no AI company, under this exact name.** The only
  corporate holder is **Escapement Consulting Limited**, a UK private company incorporated
  2022-05-23, SIC 62020 (IT consultancy) — a small consultancy, not a product brand.
- *Domains:* `escapement.com` registered 2000 (GoDaddy) and **in use — I fetched it: a book
  and music project**, an arts site, no sector overlap. `escapement.ai` registered
  2024-10-29 via Namecheap, **and it expires 2026-10-29 — five weeks from now** — currently
  serving a ~3KB page with no title. Worth watching; it may drop.
- *Registries:* **This is the problem.** npm **`escapement` is live and recent** — v0.2.0,
  last modified **2026-08-31**, described as *"Deterministic agent orchestration: an explicit
  state machine, a token-budgeted context assembler, and trajectory-grading evals with CI
  regression gates."* The matching GitHub repo is `alexander-vyh/escapement`. PyPI taken,
  `github.com/escapement` taken.

**Strongest argument against.** **There is already an active AI project with this exact name,
in an adjacent field, shipping now.** Not a company and not funded — but "deterministic agent
orchestration" is close enough to our own vocabulary that an investor or engineer searching
the name in 2026 lands on it, and it owns the npm and GitHub handles we would want. Separately,
the word's first morpheme is **"escape,"** which points the wrong way for a product whose entire
promise is that you *cannot* get away; and in French *échappement* means **exhaust pipe** (*pot
d'échappement*), while Spanish *escape* means leak or exhaust — so the European read is
automotive, not horological. Finally, at three-to-four syllables it is the longest name here,
and the metaphor needs one sentence of explanation before it lands, which is one sentence more
than a name should need on stage.

---

### 4 · TACET

**What it means.** Latin, *"it is silent."* In a musical score, **tacet** is the instruction
to a performer that they **do not play in this movement**. It is how a composer tells someone,
with complete formality and no rudeness whatsoever, to stop.

**First read.** A short, clean, slightly technical word. Musical-notation register — precise
and understated.

**The easter egg.** The best in this document, and the most deniable. Karen does not tell you
to shut up; she marks your part *tacet*. There is also a second, accidental layer: the
homophone **"tacit"** — the unspoken thing everyone in the meeting already knows.

**Memorability.** Two syllables. Short enough to say a hundred times a day.

**Availability.**
- *Companies:* **No software company found.** Searches return only the phonetically similar
  **Tacit** brands — Tacit Software (Palo Alto, founded 1997, **acquired by Oracle in November
  2008**, folded into Oracle Beehive, backed by DFJ and In-Q-Tel) and Tacit Networks (defunct
  2006). Separately, **Tacet is a well-known German audiophile classical record label** — not
  a sector conflict, but it owns the name's search results in music.
- *Domains:* `tacet.com` nameservers are `ns1.afternic.com` → **parked and listed for sale**;
  the page returns 114 bytes with no title, confirming no operating site. `tacet.ai` registered
  via GoDaddy.
- *Registries:* **npm `tacet` free (404). PyPI `tacet` free (404).** `github.com/tacet` taken.

**Strongest argument against.** **Nobody knows the word, and the word they do know is
"tacit."** That is a double failure on criterion 2: a listener cannot spell it after one
hearing because they will write the more common homophone, and a reader who does see it
spelled will assume it is a typo for *tacit* — the worst possible reaction to a brand, since
it makes the company look careless before anyone has seen the product. The reference also
requires music-notation literacy to decode, so for most of the audience the name carries no
meaning at all and the easter egg simply never fires. And the *Tacit Software → Oracle*
lineage is a genuine phonetic-confusion trademark risk in exactly our classes, not a distant
one.

---

### 5 · PLENARY

**What it means.** A **plenary session** is the part of a conference or assembly attended by
*everyone* — full, undivided, the meeting proper. Institutional vocabulary, universally
understood in EU and UN contexts.

**First read.** Serious, institutional, unambiguously about formal meetings. Zero joke risk.
Of every candidate here this is the easiest to say on stage and the easiest to spell.

**The easter egg.** Essentially none. Plenary is neutral and procedural — it carries no
strictness and gives Karen nothing to hide behind. Against the brief's fourth criterion that is
arguably *safe*; against the first three it is simply flat.

**Memorability.** Excellent. Three syllables, known word, and it travels better than anything
else here: *plénière* (FR), *plenaria* (ES/IT), *Plenum* (DE), *plenaire* (NL).

**Availability — and this is why it is fifth, not first.**
- *Companies:* **`plenary.ai` is a live AI company.** I fetched it: **PlenaryAI**, medical
  imaging and machine learning — *"Machine Learning for Improved Clinical Outcomes,"*
  **"Precision as a Service™"** — with stated ties to Johns Hopkins University and the
  University of Maryland Medical Center, and a named product, PL01. A ™ claim on their tagline
  means they are thinking about marks. Separately, **`plenary.com` is Plenary Group**, a large
  multinational infrastructure investor, developer and manager (Australia / Canada / US) — a
  189KB live corporate site and a well-resourced brand owner.
- *Domains:* `plenary.com` registered 1996 (GoDaddy), in use by Plenary Group. `plenary.ai`
  registered 2020-04-06 (Namecheap), in use by PlenaryAI. Neither is obtainable.
- *Registries:* npm `plenary` taken — a trivial personal frontend-utils package, v0.0.2, 2025.
  PyPI taken. `github.com/plenary` taken.

**Strongest argument against.** **It fails criterion 1, which the brief calls the hard filter.**
There is an existing AI company on the exact `.ai` domain and a large multinational on the `.com`.
Neither competes with us directly — medical imaging and infrastructure finance are both far away —
but "not heavily used" is not satisfied when both primary domains host live businesses and one of
them is an AI company. On top of that, **"plenary" is arguably descriptive of meeting software**,
which is the distinctiveness trap flagged in §1, and it has no second layer at all. It is listed
because it is genuinely the most pronounceable and most internationally robust name found — if the
availability picture were different it would rank first, and that is worth recording.

---

## 3 · Ranking summary

| # | Name | Criterion 1: not crowded | 2: say/spell | 3: enterprise read | 4: easter egg | Verdict |
|---|---|---|---|---|---|---|
| 1 | **Decorum** | Good — no verifiable AI/meetings incumbent; all US word marks cancelled, all in home decor; one live filing is "DECORUM LIFESTYLE", class unretrieved | Excellent | Excellent | Strong, and properly buried | **Recommended** |
| 2 | **Cloture** | **Best** — `.ai` unregistered, npm + PyPI free, zero tech incumbents | Weak — "closure" trap, split pronunciation | Very good | Strongest procedural fit | Viable if the spelling tax is accepted |
| 3 | **Escapement** | Fair — no company, but a live 2026 AI-agent project owns npm + GitHub | Good | Good | Good | Viable; watch `escapement.ai` (expires 2026-10-29) |
| 4 | **Tacet** | Good — npm + PyPI free, `.com` for sale, no software incumbent | **Poor** — reads as a typo of "tacit" | Fair | Best in list, but rarely fires | Long shot |
| 5 | **Plenary** | **Poor** — PlenaryAI on `.ai`, Plenary Group on `.com` | **Best** | **Best** | None | Recorded for completeness |

---

## 4 · Killed candidates

Generated across coined words, repurposed real words, compounds, classical and Latin roots,
parliamentary vocabulary and time/clock metaphors. One line each on cause of death.

### Killed by an incumbent (verified by search)

| Name | Why |
|---|---|
| **Rostrum** | Three AI companies already: `rostrum.dev` (AI engineering playbooks), `rostrum-ai.pro` (enterprise knowledge AI), `RostrumAI` on GitHub — plus Rostrum Pacific (music AI) and a pitch-video platform. Badly crowded in our exact sector. |
| **Quorum** | Three enterprise software incumbents, one with $100–500M revenue: Quorum Software (energy, Houston, ~1,500 customers), Quorum (`quorum.us`, AI public-affairs platform), Quorum Information Technologies (automotive SaaS). |
| **Portcullis** | Portcullis AI (`portcullisai.com`, AI code governance), Portcullis Security (`portcullis-security.ai`), Cisco-acquired Portcullis, plus an AAAI 2025 paper on an LLM privacy gateway. |
| **Rubric** | Rubric AI (**YC W26**, reasoning infrastructure for AI agents), Rubric Labs (applied AI lab), `rubric.com` (enterprise localization). Saturated. |
| **Baton** | Three enterprise-software companies: Baton AI (2024, SF, Lobby Capital/Pear VC), Baton Technologies ($12.5M raised), Baton/Ryder (supply-chain AI). |
| **Conclave** | Conclave (M&A deal-room AI), `conclave.io` (blockchain/AI engineering), Conclaves.AI. Also heavily salient from the 2024 film. |
| **Convoke** | Convoke Systems — a real, profitable US **SaaS** company in debt recovery, almost certainly holding a live class-42 mark. Semantically excellent otherwise; that is precisely the wrong kind of neighbour. |
| **Cathedra** | One letter from **Cathedral**, which raised **$160M at $1.4B** (a16z + Sequoia) for military AI. Also Cathedra Bitcoin, publicly traded. Unwinnable adjacency. |
| **Quorate** | npm `quorate` is a live *"multi-provider AI code review council CLI"* (July 2026); also inherits Quorum's confusion, and is unknown in the US. |
| **Metronome** | Metronome is a well-funded usage-based-billing company on `metronome.com`; `metronome.ai` is registered (2018, Digital Privacy Corporation). |
| **Cadence** | Cadence Design Systems — a multi-billion-dollar public company. Non-starter. |
| **Convene** | Convene (Azeus) is **board-meeting management software** and Convene is also a large coworking brand. The worst possible collision: directly inside our own adjacency. |
| **Assembly** | AssemblyAI is a major speech-to-text company — our exact technical adjacency. |
| **Clockwise** | Clockwise is an established AI calendar-optimization company. Closest adjacent competitor namespace; do not go near it. |
| **Turnstile** | Cloudflare Turnstile. |
| **Sentinel** | SentinelOne, Microsoft Sentinel. |
| **Coda** | Coda.io — a large document/workspace company, directly adjacent. |
| **Vellum** | Vellum AI, an established LLM tooling company. |
| **Agora** | Agora.io — real-time voice and video SDKs. Our exact infrastructure layer. |
| **Tribune** | Tribune Media / Tribune Publishing. |
| **Hansard** | Hansard Global plc (LSE-listed) holds the commercial name; the parliamentary sense belongs to an institution. |
| **Sandglass** | Two IT-services firms already use it (Sandglass Systems, Sandglass LLC) — direct sector collision — and the name is too soft for enterprise. |
| **Seriatim** | No software incumbent, but Seriatim Inc. (NY, since 1999) holds `seriatim.com`, and four syllables of Latin legalese fails "spellable after one hearing." |
| **Chime / Cadence / Tenet / Presidio / Threshold / Slate / The Verge** | Amazon Chime; Cadence; Tenet; Presidio (large IT integrator); Threshold Network (crypto); Slate; The Verge. All occupied. |

### Killed on the name itself — no search needed

| Name | Why |
|---|---|
| **Agendum** | Lovely pedantic easter egg (the correct Latin singular of *agenda* — peak Karen), but **merely descriptive** of meeting software. Weak mark, likely USPTO refusal. Also `agendum.com` and `.ai` are both parked on Afternic. |
| **Timebox / Timekeeper / Floorclock / Punctual** | Same descriptiveness trap. Describes the feature; cannot be defended as a brand. |
| **Writ · Arbiter · Bench · Curia · Praetor · Docket · Tribunal** | **Judicial** vocabulary — walks straight back into the legal-AI collision we are leaving, and into the most contested trademark territory in AI. |
| **Guillotine** | The genuine UK parliamentary term for a motion cutting off debate. Semantically perfect, imagery fatal. |
| **Mace** | The Westminster equivalent of the gavel, but it is a weapon and a pepper-spray brand. |
| **Lictor** | The Roman officer who cleared the way carrying the *fasces*. Fascism. |
| **Censor** | The Roman magistrate who regulated public conduct — but the modern word is censorship. |
| **Warden / Curfew / Discipline** | Carceral and authoritarian. We are selling to the people being interrupted. |
| **Moot** | "Moot point" means *irrelevant*. Fatal inversion of the product's claim. |
| **Parley** | Phonetically identical to **Parler**. Toxic political association. |
| **Dixi** | Latin "I have spoken" — a superb close for Karen, and a homophone of **Dixie**. Dead in the US. |
| **Rota** | *Rota* is Spanish for "broken" (feminine); also a Vatican court and a town in Spain. |
| **Ordo** | Ordo Iuris, Ordo Templi Orientis. Poisoned. |
| **Horae / Horarium** | The Greek goddesses of the hours and of good order — the perfect meaning, ruined by an English-speaker's first reading of "hor-". |
| **Ratchet** | Derogatory slang in AAVE. |
| **Rigor** | *Rigor mortis* in US English. |
| **Divan** | The Ottoman council of state, and a sofa. |
| **Diet** | A real legislature (Japan, Worms) and a weight-loss word. |
| **Clepsydra · Punctilio · Comitia · Aedile · Pnyx · Caesura · Foliot · Epistates** | All defensible in meaning, none survives "easy to say and spell after hearing it once." |
| **Althing · Witan · Erskine · Woolsack · Tynwald** | Too obscure, or read as a surname, or require a paragraph of explanation. |
| **Prorogue** | Carries 2019 UK constitutional-crisis baggage. |
| **Standing Order** | A recurring bank payment in the UK. |
| **Orderly** | A hospital porter. Low status. |
| **Airtime / Floortime** | Airtime (Sean Parker's app); Floortime is an established child-development therapy method. |
| **Ordris · Agendo · Quorra · Ordana · Verba · Rostra** | Coined filler. None reached a quality bar worth screening; *Tempora* additionally was GCHQ's mass-surveillance programme, which is a poor look for an enterprise product that listens to meetings. |

---

## 5 · Recommendation and what happens next

**Recommend DECORUM**, with **CLOTURE** as the live alternative if the team decides the
procedural precision is worth the spelling tax.

The case for Decorum in one paragraph: it is the only candidate that is strong on all four
criteria at once. Its first read is unambiguously enterprise, it spells itself, no AI or
meetings company holds it, every US trademark under the name is cancelled and none was ever in
software, and its prim register does the Karen work entirely through tone — which is exactly
what "easter egg only" means. Cloture beats it on availability and on semantic precision and
loses on the one thing a name has to do in a room.

**Before anyone commits, in this order:**

0. **Thirty-second free check first:** look up serial **99536798** on
   [tsdr.uspto.gov](https://tsdr.uspto.gov/). It is the only live DECORUM-family filing found
   and its class is the one fact that could move Decorum off the top of this list. If it is
   class 20/35 it is decor noise; if it is class 9 or 42, re-rank before spending anything.
1. **Paid trademark clearance** on the chosen name — Class 9, 42 and 38, US and EU. §0 explains
   why nothing in this document substitutes for it. This is the gate; do not design a logo first.
2. **Price `decorum.com`** — it is parked on Efty and therefore genuinely for sale. Get the
   number before deciding, because it may change the ranking on its own. If it is unaffordable,
   the fallback is `decorum.ai` (registered, stale placeholder, expires 2028 — approach the
   holder) or a modifier domain, which is a materially worse outcome and should be weighed then,
   not now.
3. **Watch `escapement.ai`** — it expires **2026-10-29**, about five weeks out. If Escapement
   moves up the list for any reason, that is the window.
4. **Secure the handles on the day the name is chosen**, not after: npm, PyPI, GitHub org, and
   the social handles. Cloture and Tacet both have npm and PyPI free *today*; that is a
   perishable advantage.
5. **Say the shortlisted name out loud** in the actual pitch sentences before signing off —
   *"Decorum refuses to book a meeting without an agenda"* — and have someone who has never
   seen it written spell it back. That test is what demotes Cloture, and it should be run
   properly rather than assumed.


---

## 6 · Decision

**CLOTURE**, chosen by Vitaly on 2026-09-22, after reading the argument against it.

Not Decorum. The "decor" misread was the deciding factor, and Cloture's availability is the
best in this document by a wide margin — `cloture.ai` unregistered, npm and PyPI both free,
no technology incumbent anywhere under the name.

What was accepted along with it, eyes open:

- The **"closure" spelling trap**. Every conference badge and sales call pays it.
- **Split pronunciation** — KLOH-cher vs klo-TYOOR.
- ***Clôture* is French for fence**, and `cloture.com` is a French fencing shop. Selling into
  European enterprise, this is the meaning a French speaker reaches first. The saving grace,
  *clôture de la séance*, is the second meaning, not the first.

The repository stays `gavel`. Container images, PulseAudio sink names, the stage tab title
and every internal document keep the old name — renaming them buys nothing and costs a
re-test of a demo that is days away. Cloture is the name on the **decks and the human-facing
documents**, and nowhere else, until someone decides otherwise.

Karen stays Karen. The product is Cloture; the chair in the room is Karen. That is the
easter egg working as briefed.

### Perishable — do these today

`cloture.ai` was unregistered and `cloture` was free on npm and PyPI **as of 22 September
2026**. That was the single strongest argument for the name and it is a race, not a right.
Also note this document is published on a **public** repository, which means the list of
free assets is public too.

1. Register `cloture.ai` (~$70/yr). Also worth `cloture.com` — but it is a live French
   e-commerce site, so expect it to be expensive or unavailable.
2. Claim `cloture` on npm, PyPI and as a GitHub org. Minutes of work, free.
3. **Paid trademark clearance, Class 9 + 42 + 38, US and EU.** §0 explains why nothing in
   this document substitutes for it. This is the gate before any logo goes on anything
   permanent — the wordmark shipped alongside this decision is deliberately typographic and
   cheap to redo for exactly that reason.
