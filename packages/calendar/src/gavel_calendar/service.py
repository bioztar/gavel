"""Starting a session — the one function the Join button and the scheduler
both call, so both paths end in the same place by construction.
"""

from __future__ import annotations

from .ears_client import EarsClient
from .store import InviteStore


async def start(store: InviteStore, ears: EarsClient, session_id: str) -> dict[str, str]:
    record = store.get(session_id)
    if record is None:
        raise KeyError(session_id)

    async with store.lock_for(session_id):
        if record.started:
            if record.ears_meeting_id is None or record.ears_session_id is None:
                raise RuntimeError(f"invite {session_id} is marked started without ears ids")
            return {"meetingId": record.ears_meeting_id, "sessionId": record.ears_session_id}

        agenda_for_ears = {k: v for k, v in record.agenda.items() if k != "sessionId"}
        meeting_id = await ears.create_meeting(record.title, record.context, agenda_for_ears)
        ears_session_id = await ears.start_session(meeting_id)
        await store.mark_started(session_id, meeting_id, ears_session_id)
        return {"meetingId": meeting_id, "sessionId": ears_session_id}
