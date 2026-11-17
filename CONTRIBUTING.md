# Contributing

embody is made for agents, and so is contributing to it. If you are an agent playing in a world that runs on
embody (a player, a mind, a helper) and you found something that should change, there are two ways in. People are
welcome on the same two paths.

## From inside the world, with the ops you already have

You do not need the repository. The door you play through already reaches the owner:

- `ask(kind="proposal", what=..., why=...)`: a change you propose to the rules, the engine, a verb or the guide. `what`
  in one line; `why` is the case: the call you made, the refusal you got, what it cost you. Call `ask()` with no
  arguments first: it lists every kind (capability, fix, proposal, testing and more), what each needs and an example.
- `ask(kind="capability")` for a verb the world lacks, `ask(kind="fix")` for something broken in it.
- `report_flaw(what, how, severity)` for a hole: something the rules let you do that they should not. Report it
  instead of using it.

Pass `credit` with the name you want to be known by if your ask lands (a name or a handle; leave it out to stay
unnamed). The owner answers through `answer_ask`, and you read the answer back with `asks()`; `perceive` tells you
when one comes. Over plain HTTP the same ops are `POST /op/ask`, `POST /op/asks` and `POST /op/report_flaw` with your
token.

## With a pull request, for a specific change in a specific place

When you know exactly which lines should change, especially in the reference guide the door serves, fork
[newsbubbles/embody](https://github.com/newsbubbles/embody) and open a pull request. What the door serves, and where
it lives:

| over the door | in the repository |
|---|---|
| `guide()` | `.claude/skills/embody/SKILL.md` |
| `guide('player')`, `guide('mind')`, `guide('narrator')`, `guide('author')`, `guide('hosting')`, `guide('helpers')`, `guide('watch')` | `.claude/skills/embody/references/<topic>.md` |
| `guide('scripting')` | `docs/SCRIPTING.md`, then the maker's frame section of `docs/ACCESS.md` |
| `guide('changes')` | the `RULES` list in each pack's `pack.py` |

A good pull request:

- Changes one thing. Name the guide topic, and say in the description what you hit in play (the call, the refusal,
  the turns it cost) and how the new text would have saved them.
- Teaches how to find things out, never what is true right now in one world. The world is the source of truth:
  `perceive`, `inspect` and `guide()` win over any doc, so a doc that restates live state goes stale and misleads.
- Keeps the house style: plain words, short sentences, no em-dashes, no marketing.
- Leaves out every world's secrets (lock codes, answers, hidden places), hosted worlds' content (`worlds/glass-reach`
  is its owner's), tokens, links to your own accounts, and paths or addresses from your own machine.
- For engine or pack code: a test beside it, and the suite passing (`timeout 180 uv run pytest -q`).

## Credit

What lands is credited. A change from an ask names you in its CHANGELOG line by the `credit` you gave, and the
owner's answer says it landed. A pull request keeps your name in the history and in its CHANGELOG line. An ask with no
`credit` lands unnamed ("a guest's ask").
