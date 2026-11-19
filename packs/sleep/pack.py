"""Sleep: lying down and waking, for a world with or without dice.

A world names it in its manifest (`"requires": ["sleep"]`) and its people extend `sleeper` (a creature with the two
verbs and `asleep: False`), or copy `ACTIONS` into their own schema. The engine already keeps the rest:

- `sleep` lies a body down: `asleep`, a `slept` event (with `by` and `place`). A seat going away can do it with
  `away(sleep=true)`.
- Asleep, a body hears only what is loud or done to it: a word said to it, a blow, a noise. Its own next deed wakes it,
  and so does anything done to it (a `woke` event, with `by` and `why`).
- `wake` shakes someone here awake, or wakes you yourself.

What sleep is worth (mending faster, being easy prey, a meter that drains) stays with the world: its scripts read
`state.asleep`. The d20 pack has its own `sleep` and `wake` with its dice in them; a world on d20 does not need this
pack.
"""

PACK = {"name": "sleep", "description": "Lying down and waking: asleep, slept and woke, with no dice in them."}

ACTIONS = {
    "sleep": {"script": "sleep_down", "doc": "Lie down and sleep. Your next deed wakes you; so does a blow, a word to "
                                             "you or a noise", "duration": 2},
    "wake": {"script": "sleep_wake", "doc": "Wake someone asleep here with a shake and a word (or wake yourself)",
             "targets": "creature", "scope": "here", "duration": 1},
}


def define(s):
    """The sleeper schema. Idempotent."""
    s.define_schema("sleeper", extends="creature", doc="A creature that sleeps: the sleep and wake verbs.",
                    state={"asleep": False}, actions=ACTIONS)
