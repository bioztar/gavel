"""Turn a recorded session into the brain's replay fixture (plan chunk E4).

    just export-replay                       # latest session → stdout
    just export-replay <session-uuid> > ../contract/fixtures/replay.jsonl

Output matches packages/contract/fixtures/replay.jsonl: one frame per line,
`atMs` relative to the first frame, absolute `at`/`atMs` stripped.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from ears.db.models import CallSession, Event
from ears.settings import get_settings


async def main() -> None:
    engine = create_async_engine(get_settings().postgres_dsn)
    async with engine.connect() as conn:
        if len(sys.argv) > 1:
            session_id = uuid.UUID(sys.argv[1])
        else:
            row = await conn.execute(
                select(CallSession.id).order_by(CallSession.started_at.desc()).limit(1)
            )
            found = row.scalar_one_or_none()
            if found is None:
                sys.exit("no sessions recorded yet")
            session_id = found
        rows = await conn.execute(
            select(Event.frame).where(Event.session_id == session_id).order_by(Event.id)
        )
        frames = [r[0] for r in rows]
    await engine.dispose()

    if not frames:
        sys.exit(f"session {session_id} has no events")
    t0 = frames[0]["atMs"]
    for frame in frames:
        rel = frame["atMs"] - t0
        body = {k: v for k, v in frame.items() if k not in {"at", "atMs"}}
        print(json.dumps({"atMs": rel, **body}))
    print(f"{len(frames)} frames from session {session_id}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
