# concierge — side A

The Discord bot people talk to. Owns everything before and after the call: the intake
conversation, collecting what attendees know, drafting the agenda, and posting the
minutes afterwards.

Also the entry point a stranger hits cold — Mastra's judge will DM this bot from their
own phone with no context, so the no-context path has to be good and it has to be
hosted somewhere public that stays up until 17:30 Sunday.

Produces the agenda described in [../../docs/CONTRACT.md](../../docs/CONTRACT.md) and
hands it to the Chair. Consumes call events back.

Chunks A1–A8 in [../../docs/PLAN.md](../../docs/PLAN.md).

## Env

`DISCORD_CONCIERGE_TOKEN`, `NEBIUS_API_KEY`, `CHAIR_BASE_URL`, `SEAM_SHARED_SECRET`.

## Build against a fake Chair

Do not wait for side B. A stub that accepts `POST /v1/sessions` and returns the state
shape from the contract is enough to build the whole of A against.
