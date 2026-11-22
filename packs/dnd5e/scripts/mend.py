use("common")
use("five")
# In 5e rest does not mend a point a beat: hp come back from rests, spells and medicine. What this tick keeps: a stable
# body wakes at 1 hp when its 1d4 hours are up, and the days forgive the blows a faction remembers.

def tick(ctx):
    me = ctx.self
    st = me.state
    if st.dead:
        return
    if st.bruised_with:
        forgive_all(ctx, me)
    come_round(ctx, me)
