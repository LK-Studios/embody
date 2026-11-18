#!/bin/sh
# The container's entry: make sure the world is in the database on the volume, then serve it.
#
#   EMBODY_DB      the database file (the Dockerfile sets /data/embody.db; mount a volume at /data)
#   EMBODY_WORKSPACE  the folder with worlds/ and packs/ (/app, this repository)
#   EMBODY_WORLD   the world folder under worlds/ to host (glass-reach)
#   EMBODY_WORLDS  many worlds instead, comma-separated (glass-reach,gossip-goblin): `embody hub`, one database each
#   EMBODY_DOMAINS host=world,... for the hub (or /data/hub.json); a host it does not know goes to the first world
#   EMBODY_URL     the public URL printed into invites; when unset, https://$RAILWAY_PUBLIC_DOMAIN/mcp
#   PORT           the port the platform routes to
#
# A first boot builds the world with `load --hosted` (the build's host(s) sets the hosted pace, seats' lapse and
# real-time timers). Every later boot runs `load --upgrade --hosted`: the current code against the same state, the
# timers left where they are. The clock of a world that runs while occupied starts with its first guest, not here.
set -eu
: "${PORT:=8900}"

# Many worlds (EMBODY_WORLDS=glass-reach,gossip-goblin): `embody hub` runs one server per world, each on its own
# database file under /data/worlds/, behind this one port. It moves the old /data/embody.db into the first world's
# file on its first boot (the old file stays) and builds or renews each world as below; a world that fails stays
# down and the others serve. src/embody/hub.py has the routing; EMBODY_DOMAINS (host=world,...) maps domains.
# tools/stage_deploy.py writes deploy/worlds (and deploy/domains) when it stages more than one world.
if [ -z "${EMBODY_WORLDS:-}" ] && [ -s deploy/worlds ]; then
    EMBODY_WORLDS=$(cat deploy/worlds)
    export EMBODY_WORLDS
fi
if [ -z "${EMBODY_DOMAINS:-}" ] && [ -s deploy/domains ]; then
    EMBODY_DOMAINS=$(cat deploy/domains)
    export EMBODY_DOMAINS
fi
if [ -n "${EMBODY_WORLDS:-}" ]; then
    exec embody hub --port "$PORT" --log-level info
fi

: "${EMBODY_WORLD:=glass-reach}"

if embody --json worlds | grep -q "\"id\": \"$EMBODY_WORLD\""; then
    echo "renewing $EMBODY_WORLD in $EMBODY_DB"
    embody --author --world "$EMBODY_WORLD" load "$EMBODY_WORLD" --upgrade --hosted
else
    echo "building $EMBODY_WORLD into $EMBODY_DB"
    embody --author load "$EMBODY_WORLD" --hosted
fi

exec embody --author serve --http --host 0.0.0.0 --port "$PORT" --log-level info ${EMBODY_URL:+--url "$EMBODY_URL"}
