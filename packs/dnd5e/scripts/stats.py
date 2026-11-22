use("common")
use("five")
# Your own numbers, as the rules read them now.

def apply(ctx):
    me = ctx.actor
    st = me.state
    abil = {}
    for ab in ["str", "dex", "con", "int", "wis", "cha"]:
        abil[ab] = [score(me, ab), amod(me, ab)]
    attacks = []
    for it in held_things(me):
        if not it.state.weapon:
            continue
        rng = bool(it.state.ranged) and "thrown" not in props(it)
        dice = damage_dice(me, it) or str(flat_damage(it))
        m = amod(me, weapon_ability(me, it, rng)) + int(it.state.bonus or 0)
        attacks.append({"with": it.name, "to_hit": attack_bonus(ctx, me, it, rng), "damage": dice + ("+" + str(m) if m > 0 else (str(m) if m < 0 else "")),
                        "type": it.state.dtype or "bludgeoning", "ranged": rng})
    um = amod(me, weapon_ability(me, None, False))
    attacks.append({"with": "bare hands", "to_hit": attack_bonus(ctx, me, None, False),
                    "damage": (st.martial_arts + "+" + str(um)) if st.martial_arts else str(max(0, 1 + um)), "type": "bludgeoning"})
    out = {"hp": st.hp, "max_hp": st.max_hp, "temp_hp": st.temp_hp or 0, "ac": armor_class(ctx, me), "prof": prof(me),
           "level": st.level, "class": st.cls, "initiative": amod(me, "dex") + int(st.init_bonus or 0),
           "abilities": abil, "saves": st.saves or [], "attacks": attacks, "attacks_per_action": attacks_per_action(me),
           "conditions": sorted(list(conds(ctx, me).keys())), "exhaustion": st.exhaustion or 0,
           "hit_dice": st.hit_dice, "hit_die": st.hit_die}
    out["skills"] = skill_mods(ctx, me)
    out["passive_perception"] = passive_perception(ctx, me)
    out["statblock"] = statblock(ctx, me)
    sc = st.spellcasting or {}
    if sc:
        out["spells"] = {"known": sc.get("spells") or [], "slots": sc.get("slots") or {}, "dc": save_dc(me),
                         "attack": prof(me) + cast_mod(me), "ability": sc.get("ability")}
    if st.concentrating:
        out["concentrating"] = st.concentrating.get("spell")
    if st.down and not st.dead:
        out["dying"] = bool(st.dying)
        out["death_saves"] = st.death_saves
    f = my_fight(ctx, me)
    if f is not None:
        out["fight"] = {"round": f.state.round, "order": order_text(ctx, f), "your_turn": f.state.turn_of == me.id,
                        "left": turn_left(ctx, me) if f.state.turn_of == me.id else []}
    line = "hp " + str(st.hp) + "/" + str(st.max_hp) + ", AC " + str(out["ac"]) + ", prof +" + str(out["prof"])
    line = line + "; " + "; ".join([a["with"] + " " + ("+" if a["to_hit"] >= 0 else "") + str(a["to_hit"]) + " (" + a["damage"] + " " + a["type"] + ")" for a in attacks])
    if out["conditions"]:
        line = line + "; " + ", ".join(out["conditions"])
    if f is not None:
        line = line + "; round " + str(f.state.round) + ": " + order_text(ctx, f)
    ctx.log(line)
    return out
