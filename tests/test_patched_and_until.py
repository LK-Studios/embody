"""Three fixes from a world's playtest. A patch to your own body shows you what changed, never its secret list, its
rules, its space or the host's policy (a rule growing `secret` named every hidden field to the player). A conditional
wait reads past an event whose payload names several people at once. A wait that times out comes back in the shape a
fire has, with the cursor where it stood."""

from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def seated():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.move("Prisoner", "Hall")
    sam = eng.session("sam")
    sam.join("two-rooms", "Prisoner")
    sam.wait(timeout=0)
    return eng, w, i, gm, sam


def patches(b):
    return [e["payload"] for e in b["events"] if e["kind"] == "patched"]


def test_a_patch_shows_the_change_never_the_secret_list():
    eng, w, i, gm, sam = seated()
    gm.patch("Prisoner", {"secret": ["genome", "mods"], "mood": "rinsed"})
    seen = patches(sam.wait(timeout=0))
    assert seen and all("secret" not in p["changes"] and "secret" not in p["before"] for p in seen)
    assert any(p["changes"].get("mood") == "rinsed" for p in seen)
    gm.patch("Prisoner", {"secret": ["genome", "mods", "psyche"]})
    assert not patches(sam.wait(timeout=0))  # nothing left to show: no event at all
    assert "secret" in w.events(kinds=["patched"], limit=1, newest=True)[-1]["payload"]["changes"]  # the log keeps it


def test_an_until_wait_reads_past_a_payload_naming_several():
    eng, w, i, gm, sam = seated()
    w.emit("watched", actor=i["Guard"], target=i["Hall"], payload={"who": [i["Guard"], i["Prisoner"]], "text": "two"})
    b = sam.wait(until="heard('nothing like this')", timeout=0)
    assert b["timed_out"]


def test_a_timed_out_wait_has_the_shape_of_a_fire():
    eng, w, i, gm, sam = seated()
    b = sam.wait(until="heard('nothing like this')", timeout=0)
    assert b["timed_out"] and b["cursor"] == b["since"] and b["events"] == [] and "ambient" in b
