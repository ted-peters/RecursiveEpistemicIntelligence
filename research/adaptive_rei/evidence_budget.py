"""Single-call evidence decisions using a short instruction selected from the passage."""
import re

CAUSAL = re.compile(r"\b(cause[ds]?|responsible for|because of|attributable to)\b", re.I)
DEPENDENT = re.compile(
    r"\b(copied|derived|based on|relies on|relied on|relayed|repeated|"
    r"retracted|withdrawn|misidentified|mislabeled|mislabelled|mistaken|"
    r"calibration|invalid|obsolete|summari[sz]es|transcribed|cites?)\b", re.I
)
FORMAT = 'Use only the passage. JSON {"answer":"yes|no|uncertain"}. '


def evidence_instruction(passage):
    question, _, evidence = passage.partition("?")
    if CAUSAL.search(question):
        rule = "Timing alone cannot establish cause. Check competing explanations and controlled comparisons."
    elif DEPENDENT.search(evidence):
        rule = ("Trace each report to its original source. Discard dependent claims if that source fails. "
                "Use surviving independent evidence, else uncertain. Disproof of evidence alone is not no.")
    else:
        rule = ("Match subject, time and scope. Use uncertain for missing support or unresolved ties. "
                "An irrelevant defect cannot defeat independent evidence.")
    return FORMAT + rule


def decide(url, model, passage):
    from adaptive_rei_benchmark import predict
    return predict(url, model, evidence_instruction(passage), passage)
