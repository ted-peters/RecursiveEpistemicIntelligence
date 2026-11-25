"""A cheap eligibility test for a paid, single-statement evidence review."""
import re

STOP = frozenset("""
a an the am is are was were be been being do does did can could may might will
would should has have had of to from on in into for with at by as it its their
they them this that those these there any an and or not ever really still
you your he his she her i we us some same thing about than
""".split())


def terms(text):
    words = re.findall(r"[^\W_]+", text.casefold())
    return {w.removesuffix("s") if len(w) > 4 and not w.endswith("ss") else w
            for w in words if w not in STOP}


def lacks_overlap(question, spans):
    """Only filter longer questions; a relevant paraphrase can lack shared words."""
    wanted = terms(question)
    if len(wanted) < 3:
        return False
    needed = min(3, (len(wanted) + 1) // 2)
    return not any(len(wanted & terms(span)) >= needed for span in spans)
