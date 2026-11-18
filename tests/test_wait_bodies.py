"""A mind whose grant names several bodies hears for all of them: one wait reads what reached each body nobody else
holds, every event once, tagged `for` with the bodies it reached. A body a player holds is theirs to hear, and a mind
with one body gets its events as before, untagged."""

from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def two_posts():
    eng, w, i = engine_with_two_rooms()  # the Guard stands in the Hall, the Prisoner in the Cell
    gm = owner(eng)
    i["Visitor"] = w.spawn("creature", i["Cell"], "Visitor")
    i["Clerk"] = w.spawn("creature", i["Hall"], "Clerk")
    g = gm.invite("mind", entity="Guard", scope=["Guard", "Prisoner"], label="two-posts")
    mind = eng.session_for_token(g["token"])
    mind.join(entity="Guard")
    mind.wait(timeout=0)
    return eng, w, i, gm, mind


def test_one_wait_hears_for_every_body_and_says_which():
    eng, w, i, gm, mind = two_posts()
    w.say(i["Visitor"], "Are you awake in there?", to=i["Prisoner"])
    w.say(i["Clerk"], "Your shift, sir.", to=i["Guard"])
    got = {e["payload"]["text"]: e["for"] for e in mind.wait(timeout=0)["events"] if e["kind"] == "say"}
    assert got == {"Are you awake in there?": [i["Prisoner"]], "Your shift, sir.": [i["Guard"]]}


def test_full_carries_what_reached_only_the_other_body():
    eng, w, i, gm, mind = two_posts()
    w.say(i["Visitor"], "Are you awake in there?", to=i["Prisoner"])
    b = mind.wait(timeout=0, full=True)
    assert [e["payload"]["text"] for e in b["heard"] if e["kind"] == "say"] == ["Are you awake in there?"]


def test_a_body_someone_else_holds_is_not_heard():
    eng, w, i, gm, mind = two_posts()
    eng.session("sam").join("two-rooms", "Prisoner")
    w.say(i["Visitor"], "Are you awake in there?", to=i["Prisoner"])
    assert not [e for e in mind.wait(timeout=0)["events"] if e["kind"] == "say"]


def test_a_mind_with_one_body_is_untagged():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    i["Clerk"] = w.spawn("creature", i["Hall"], "Clerk")
    mind = eng.session_for_token(gm.invite("mind", entity="Guard", label="one")["token"])
    mind.join()
    mind.wait(timeout=0)
    w.say(i["Clerk"], "Your shift, sir.", to=i["Guard"])
    evs = [e for e in mind.wait(timeout=0)["events"] if e["kind"] == "say"]
    assert evs and "for" not in evs[0]
