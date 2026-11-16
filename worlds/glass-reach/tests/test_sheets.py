"""Players grow in the Reach: a newcomer carries a sheet that rolls what its template rolled, the NPCs keep flat
skills, a newcomer from before sheets gets one on upgrade with its ranks, and the root holds the Reach's numbers."""

from pathlib import Path

from embody.cli import load_world
from embody.ops import AUTHOR, Engine

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
SKILLS = ["blade", "brawl", "climb", "stealth", "survival", "lore", "lockpick", "aim", "parley", "resolve", "search", "track"]


def reach():
    eng = Engine(workspace=REPO)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "glass-reach")
    root = gm.summary()["root"]
    gm.patch(root, {"check_again_after": 0})  # the same check read again and again
    return eng, gm, root


def mods(seat):
    return {k: seat.act("check", params={"skill": k, "dc": 1})["result"]["mod"] for k in SKILLS}


def test_a_newcomer_carries_a_sheet_that_rolls_what_its_template_rolled():
    eng, gm, root = reach()
    rules = gm.inspect(root)["state"]["sheet_rules"]
    assert {k: rules[k] for k in ("per_target_day", "rank_cost", "max_rank", "self_taught")} == \
        {"per_target_day": 1, "rank_cost": 15, "max_rank": 5, "self_taught": 2}
    for tpl, name in (("carrier", "Cal"), ("guard", "Gus"), ("keth", "Kit"), ("dreyer", "Dev")):
        seat = eng.session(name.lower())
        seat.join("glass-reach", template=tpl, name=name)
        st = gm.inspect(name)["state"]
        assert st["sheet"]["skills"] == st["skills"]
        gm.patch(name, {"skills": {"search": 2, "track": 1}, "sheet": {"skills": {"search": 2, "track": 1}}})
        with_sheet = mods(seat)
        gm.patch(name, {"sheet": None})
        assert mods(seat) == with_sheet, tpl
    assert "sheet" not in gm.inspect("Captain Ruhl")["state"]  # the NPCs keep flat skills


def test_a_newcomer_from_before_sheets_gets_one_on_upgrade_with_its_ranks():
    eng, gm, root = reach()
    harl = eng.session("harl")
    harl.join("glass-reach", template="guard", name="Harl")
    gm.patch("Harl", {"sheet": None, "skills": {"blade": 2, "resolve": 1, "survival": 1}})
    before = mods(harl)
    load_world(gm, "glass-reach", upgrade=True)
    assert gm.inspect("Harl")["state"]["sheet"]["skills"] == {"blade": 2, "resolve": 1, "survival": 1}
    assert mods(harl) == before
