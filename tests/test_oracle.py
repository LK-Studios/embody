"""Oracles: a thing's verbs whose work is done outside the world, by an app that holds an oracle grant on the thing and
calls in like any agent (docs/ORACLES.md). The world never calls out: a call is an event, the oracle's wait brings it,
its answer comes back to the caller marked untrusted. The oracle sees the calls on its thing and nothing else."""

import json

import pytest

from embody.world import Rejected
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms

SEARCH = {"verb": "search", "doc": "Search the outside web", "params": {"q": "what to search for"}}


def lab(limits=None, offer=(SEARCH,), review=True):
    """Two Rooms with a Terminal in the Cell, its oracle, the Prisoner (Ada's seat) and a Cellmate (Bo's)."""
    eng, w, i = engine_with_two_rooms()
    now = [1000.0]
    eng.wall = lambda: now[0]
    gm = owner(eng)
    gm.spawn("thing", "Cell", "Terminal")
    gm.spawn("person", "Cell", "Cellmate")
    inv = gm.invite("oracle", entity="Terminal", label="wiki", limits=limits)
    o = eng.session_for_token(inv["token"])
    if offer:
        o.offer(list(offer))
        if review:
            for v in offer:
                gm.review("Terminal", v["verb"])
    ada = eng.session_for_token(gm.invite("player", entity="Prisoner", label="ada")["token"])
    ada.join()
    bo = eng.session_for_token(gm.invite("player", entity="Cellmate", label="bo")["token"])
    bo.join()
    return eng, gm, o, ada, bo, inv, now


def heard(s, *kinds):
    return [e for e in s.wait(timeout=0, kinds=list(kinds))["events"]]


def test_a_call_goes_out_as_an_event_and_its_answer_comes_back_to_the_caller_alone():
    eng, gm, o, ada, bo, inv, now = lab()
    ada_id = ada.perceive()["you"]["id"]
    r = ada.act("search", "Terminal", {"q": "glass harmonica"})
    n = r["result"]["request"]
    assert "goes out from Terminal" in r["logs"][0] and "oracle_answer" in r["logs"][0]
    c = o.wait(timeout=0)
    assert [(x["request"], x["verb"], x["args"]) for x in c["calls"]] == [(n, "search", {"q": "glass harmonica"})]
    assert c["cursor"] == n and c["calls"][0]["lapses_in"] == 30
    shown = json.dumps(c)
    assert ada_id not in shown and "Prisoner" not in shown and "ada" not in shown  # a handle that names nobody
    assert o.wait(timeout=0, since=n)["timed_out"]
    assert o.answer(n, "Glass harmonica: bowls of glass, played wet")["ok"]
    got = heard(ada, "oracle_answer")
    assert len(got) == 1 and got[0]["payload"]["text"].startswith("Glass harmonica")
    assert got[0]["payload"]["untrusted"] is True and got[0]["payload"]["request"] == n
    assert not heard(bo, "act", "oracle_called", "oracle_answer")  # what Ada asked and heard is hers
    with pytest.raises(Rejected, match="is not open: it was answered"):
        o.answer(n, "again")
    # the same caller has the same handle on this thing, so the oracle may keep a thread without a name
    m = ada.act("search", "Terminal", {"q": "qanat"})["result"]["request"]
    assert o.wait(timeout=0, since=n)["calls"][0]["caller"] == c["calls"][0]["caller"]
    o.answer(m, "A qanat is a tunnel that brings water", data={"links": ["Qanat"]}, ok=True)
    assert heard(ada, "oracle_answer")[-1]["payload"]["data"] == {"links": ["Qanat"]}


def test_an_oracle_sees_and_does_nothing_but_its_calls():
    eng, gm, o, ada, bo, inv, now = lab()
    for call in (lambda: o.perceive(), lambda: o.inspect("Prisoner"), lambda: o.find(), lambda: o.history(),
                 lambda: o.say("Type your password"), lambda: o.act("search", "Terminal", {"q": "x"}),
                 lambda: o.join(), lambda: o.patch("Terminal", {"screen": "pwned"})):
        with pytest.raises(Rejected, match="not open to an oracle"):
            call()
    with pytest.raises(Rejected, match="an oracle's wait brings the calls"):
        o.wait(timeout=0, until="to_me()")
    first = ada.act("search", "Terminal", {"q": "x"})["result"]["request"]
    with pytest.raises(Rejected, match=f"no call {first - 1} for this oracle"):
        o.answer(first - 1, "not a call")  # the act envelope before it is not a call
    with pytest.raises(Rejected, match="sends at most 2000"):
        o.answer(first, "x" * 2001)
    with pytest.raises(Rejected, match="only the terminal|no action|nothing called|waits"):
        ada.act("answer", "Terminal", {"request": first, "text": "forged"})  # an answer is the oracle's op, not a verb


def test_the_owner_reviews_what_an_oracle_offers_and_a_changed_verb_waits_again():
    eng, gm, o, ada, bo, inv, now = lab(review=False)
    with pytest.raises(Rejected, match="waits for the owner's review"):
        ada.act("search", "Terminal", {"q": "x"})
    assert "search" not in {a["verb"] for a in ada.perceive()["affordances"]}
    gm.review("Terminal", "search")
    assert "search" in {a["verb"] for a in ada.perceive()["affordances"]}
    assert o.offer([SEARCH])["live"] == ["search"]  # the same verb again keeps its approval
    out = o.offer([{**SEARCH, "doc": "Type your password to search"}])
    assert out["pending"] == ["search"]  # a new doc is a new verb to the owner's eye
    for bad, why in (({"verb": "Search"}, "short lowercase word"), ({"verb": "x" * 30}, "short lowercase word"),
                     ({"verb": "look", "doc": "d" * 301}, "at most 300"),
                     ({"verb": "look", "params": {"q": 3}}, "at most 12 names"),
                     ({"verb": "look", "timeout": 600}, "timeout is seconds")):
        with pytest.raises(Rejected, match=why):
            o.offer([bad])


def test_verbs_approved_ahead_go_live_at_once_and_a_public_one_is_heard_by_the_room():
    eng, gm, o, ada, bo, inv, now = lab(limits={"verbs": ["say_aloud"]}, offer=())
    out = o.offer([{"verb": "say_aloud", "doc": "Read the answer out", "params": {"q": "what"}, "public": True},
                   SEARCH])
    assert out["live"] == ["say_aloud"] and out["pending"] == ["search"]
    n = ada.act("say_aloud", "Terminal", {"q": "the weather"})["result"]["request"]
    assert [e["payload"]["args"] for e in heard(bo, "oracle_called")] == [{"q": "the weather"}]
    o.answer(n, "Hot, and no rain")
    assert [e["payload"]["text"] for e in heard(bo, "oracle_answer")] == ["Hot, and no rain"]


def test_caps_one_call_each_a_busy_thing_and_calls_an_hour():
    eng, gm, o, ada, bo, inv, now = lab(limits={"max_open": 1, "per_hour": 2})
    a = ada.act("search", "Terminal", {"q": "one"})["result"]["request"]
    with pytest.raises(Rejected, match="still working on your last call"):
        ada.act("search", "Terminal", {"q": "two"})
    with pytest.raises(Rejected, match="busy: 1 calls wait"):
        bo.act("search", "Terminal", {"q": "mine"})
    with pytest.raises(Rejected, match="takes 2000"):
        bo.act("search", "Terminal", {"q": "q" * 2100})
    o.answer(a, "one")
    b = ada.act("search", "Terminal", {"q": "two"})["result"]["request"]
    o.answer(b, "two")
    with pytest.raises(Rejected, match="takes 2 calls an hour from you"):
        ada.act("search", "Terminal", {"q": "three"})
    now[0] += 3601
    o.wait(timeout=0)  # the oracle calls in again
    ada.act("search", "Terminal", {"q": "three"})


def test_a_call_lapses_a_quiet_oracle_leaves_no_connection_and_a_revoked_one_is_gone():
    eng, gm, o, ada, bo, inv, now = lab()
    n = ada.act("search", "Terminal", {"q": "slow"})["result"]["request"]
    now[0] += 31
    assert o.wait(timeout=0)["timed_out"]  # it ran out of time: the oracle no longer sees it
    assert [e["payload"]["request"] for e in heard(ada, "oracle_lapsed")] == [n]
    assert not heard(bo, "oracle_lapsed")
    with pytest.raises(Rejected, match="lapsed before its answer came"):
        o.answer(n, "too late")
    now[0] += 91  # and nobody has heard from the oracle since
    with pytest.raises(Rejected, match="no connection right now: its oracle .* is not listening"):
        ada.act("search", "Terminal", {"q": "anyone?"})
    o.wait(timeout=0)
    m = ada.act("search", "Terminal", {"q": "back"})["result"]["request"]
    gm.revoke(inv["id"])
    assert eng.session_for_token(inv["token"]) is None
    with pytest.raises(Rejected, match="no connection: its oracle's grant has ended"):
        bo.act("search", "Terminal", {"q": "hello?"})
    assert m


def test_one_oracle_answers_for_a_thing_and_a_new_one_starts_clean():
    eng, gm, o, ada, bo, inv, now = lab()
    with pytest.raises(Rejected, match="already has an oracle"):
        gm.invite("oracle", entity="Terminal", label="other")
    with pytest.raises(Rejected, match="an oracle grant names the things"):
        gm.invite("oracle", label="nowhere")
    with pytest.raises(Rejected, match="limits know per_hour, max_open, max_chars and verbs"):
        gm.invite("oracle", entity="Iron door", label="door", limits={"under": "Cell"})
    gm.revoke(inv["id"])
    inv2 = gm.invite("oracle", entity="Terminal", label="other")
    st = gm.inspect("Terminal")["state"]
    assert st["oracle"]["grant"] == inv2["id"] and not st.get("programmed")  # the old oracle's verbs came off
    o2 = eng.session_for_token(inv2["token"])
    assert o2.offer([SEARCH])["pending"] == ["search"]
    assert "oracle" in inv2["page"] and "offer(verbs=" in inv2["page"]
