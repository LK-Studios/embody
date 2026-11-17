"""A world's own guides: `guides` on the root puts one line on new invite pages, in the join briefing and in guide(),
for the roles it names, and nothing for the others or for a field that is not https."""

from embody.grants import guides_line
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms

GUIDES = {"url": "https://github.com/someone/world-roles",
          "base": "https://github.com/someone/world-roles/blob/main",
          "for": {"player": "roles/player.md", "mind": "https://example.org/mind.md"}, "also": ["GUIDELINES.md"]}


def test_a_world_points_its_players_at_its_own_guides():
    eng, w, i = engine_with_two_rooms()
    eng.public_url = "https://reach.example/mcp"
    gm = owner(eng)
    gm.patch(w.root_id, {"guides": GUIDES})
    gm.patch("Prisoner", {"playable": True})
    inv = gm.invite("player", entity="Prisoner", label="Sam")
    read = "https://github.com/someone/world-roles/blob/main/roles/player.md"
    assert read in inv["page"] and "blob/main/GUIDELINES.md" in inv["page"] and "pull request" in inv["page"]
    assert "This world keeps its own guides" in inv["page"]
    sam = eng.session_for_token(inv["token"])
    sam.use("two-rooms")
    how = sam.join("two-rooms", "Prisoner")["briefing"]["how"]
    assert any(read in h and "wins over any page" in h for h in how)
    assert read in sam.guide()["world_guides"] and "world_guides" not in sam.guide("player")
    narr = gm.invite("narrator", label="Keeper")
    assert "own guides" not in narr["page"]


def test_guides_need_https_and_a_file_for_the_role():
    assert guides_line(GUIDES, "mind").startswith("this world keeps") and "https://example.org/mind.md" in guides_line(GUIDES, "mind")
    assert guides_line(GUIDES, "narrator") == ""
    assert guides_line({**GUIDES, "url": "http://x.example"}, "player") == ""
    assert guides_line({**GUIDES, "for": "roles/player.md"}, "player") == ""
    assert guides_line(None, "player") == "" and guides_line("https://x.example", "player") == ""
    plain = guides_line({"url": "https://x.example/r", "for": {"player": "p.md"}}, "player")
    assert "https://x.example/r/p.md before you play" in plain
