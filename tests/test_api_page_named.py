"""The API page (/docs) is named where agents look: the invite page and the join briefing."""

from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def test_the_invite_page_and_the_briefing_name_the_api_page():
    eng, w, i = engine_with_two_rooms()
    eng.public_url = "https://reach.example/mcp"
    gm = owner(eng)
    gm.patch("Prisoner", {"playable": True})
    inv = gm.invite("player", entity="Prisoner", label="Sam")
    assert "/docs is a page of every call, grouped by layer" in inv["page"]
    sam = eng.session_for_token(inv["token"])
    sam.use("two-rooms")
    how = sam.join("two-rooms", "Prisoner")["briefing"]["how"]
    assert any("https://reach.example/docs is a page of every call" in h for h in how)
