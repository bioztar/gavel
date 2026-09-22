# Cloture — brand kit

The product is **Cloture**. The chair in the room is still **Karen**. The repository,
the container images, the PulseAudio sinks and every internal document are still `gavel`
and that is deliberate — see `docs/naming-candidates.md` §6.

This file is the contract for anyone reworking a deck or a human-facing document.

## The name

**Cloture** — the parliamentary motion that cuts off debate and forces the question.
A body saying *this has gone on long enough; we are moving to the decision.* That is the
product in one word.

- Written **Cloture**, no circumflex. `Clôture` is French for *fence*; the accent points at
  the wrong meaning and we do not use it.
- Said **KLOH-cher**. If someone says klo-TYOOR, let them.
- In running text it is a proper noun: *Cloture joins the call.* Never "the cloture",
  never lowercase, never a verb. It is not "we clotured the meeting."

### The one weakness, and how copy handles it

People will write **closure**. That is the accepted cost of the name. Mitigations, all
cheap, all mandatory:

- The wordmark is **letterspaced caps**. Do not tighten the tracking — the spacing exists
  so a reader takes the letters one at a time.
- The **first** time the name appears in any deck, gloss it once, in the copy, in the
  product's own voice. *"Cloture — the motion that cuts off debate."* Once. Never twice;
  explaining a name twice is a name apologising for itself.
- Never place the words *cloture* and *closure* in the same paragraph.

## Vocabulary

**Use — procedural, parliamentary, the register of a body conducting business.**
motion · the floor · yield · the question · put to the question · order · chair ·
the minute · standing rules · adjourn · the clock.

**Do not use — judicial.** *gavel, verdict, ruling, court, tribunal, docket, arbiter,
writ, bench, sentence, the judge.* Two reasons and both matter: Gavel is a live legal-AI
product (gavel.io, acquired by Relativity), so judicial vocabulary walks straight back into
the collision we are leaving; and a judge decides *for* you, whereas a chair makes *you*
decide, which is the entire product.

**Rework, do not find-and-replace.** Several decks lean on the gavel as an object — a
gavel comes down, a gavel is banged. Cloture has no object. It has a *moment*: debate
stops and the question is put. Sentences built on the old image have to be rewritten
around the new one, and a document where "gavel" became "Cloture" mechanically will read
as exactly that.

## The mark

`cloture-mark.svg` — a **caesura**: the notation meaning *stop here, the line is cut*,
drawn across a staff. The mark is the cut itself, not an instrument that makes it.

| File | Use |
|---|---|
| `cloture-wordmark.svg` | Default lockup, light backgrounds. 360×64. |
| `cloture-wordmark-dark.svg` | Same on dark. |
| `cloture-mark.svg` | Square, 64×64. Avatars, slide corners, app icons. |
| `favicon.svg` | The mark, no title element. Inline it as a data URI in self-contained HTML. |

Clear space around any lockup: **half the mark's height** on all sides. Minimum wordmark
width 180px. Never recolour the caesura strokes to anything but the accent, never set the
wordmark in a display or script face, never add a tagline inside the lockup.

**These are typographic and cheap on purpose.** Trademark clearance has not been done
(Class 9 + 42 + 38, US and EU — `docs/naming-candidates.md` §0). Nothing here should be
expensive to throw away.

The wordmark sets its text with `<text>` and a system font stack rather than outlined
paths. Fine in a browser, which is the only place these are used today. Before it goes on
anything printed or handed to a third party, have the letterforms outlined.

## Tokens

Paste inline. Every deck is self-contained — no external stylesheet, no webfont.

```css
:root{
  --ink:#14161a;        /* body text, the mark's ground */
  --ink-2:#3d434d;      /* secondary text */
  --mute:#6c7280;       /* captions, the staff in the mark */
  --line:#e4e2de;       /* rules, table borders */
  --paper:#faf9f7;      /* page ground, warm — not white */
  --card:#ffffff;
  --accent:#c8102e;     /* the cut. Section rules, the moment debate stops */
  --accent-soft:#fdf2f3;
  --info:#1f4fd8;       /* links and neutral callouts only */
  --info-soft:#f1f5fe;
}
```

**Red is the motion, not decoration.** `--accent` marks the place where something is cut
off, closed, or decided: section rules, the stop beat in a run of show, a hard deadline.
It is not a highlighter. A deck where everything important is red has nothing important.

Type: the system stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica,
Arial, sans-serif`), 16–17px body, line-height 1.65, max-width ~860px centred. Headings
600, never 700+. Monospace (`ui-monospace, SFMono-Regular, Menlo, Consolas`) for anything
said verbatim or typed.

Print (`@media print`): dark text on white, no shadows, `page-break-inside: avoid` on
cards and tables. Every deck must survive being printed.

## Karen

Unchanged. `assets/persona/karen-formal.png` stays the face — she is relatable and the
pitch is built around her. Do not regenerate her, do not restyle her, do not put the
wordmark on her.

Her name in the Meet roster stays **Karen**. Cloture is the product; Karen is who joins.
The joke stays an easter egg: it arrives in her register, never in the branding. No deck
explains that she is a Karen.
