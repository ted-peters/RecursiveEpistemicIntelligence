"""Compare compact evidence extraction against stored REI results and new controls."""
import json
from pathlib import Path
import adaptive_rei_benchmark as b
from adaptive_rei_engine import Evidence, evaluate

PROMPT = """Extract evidence for the question. Return exactly three JSON arrays: "yes" and "no" contain short verbatim quotes directly supporting each answer; "invalid" contains quoted items from those arrays whose source, date, subject or causal attribution is discredited. Exclude irrelevant facts. Missing evidence supplies no vote. Use [] for an empty array."""
NEW = [
("Was box N counted? The tally lists N. Its entry was duplicated from box H. No other count exists.","uncertain"),
("Was box N counted? An auditor personally counted N after discovering an error in the first tally.","yes"),
("Was desk seven occupied at three? The camera shows an occupied desk but its time setting was lost. No one can date the image.","uncertain"),
("Was desk seven occupied at three? An inspector stood beside desk seven at three and saw the empty chair and vacant desk.","no"),
("Did the banner cause more visitors to enter? The crowd grew after installation. Admission fees were waived that same day. There was no way to isolate the banner's effect.","uncertain"),
("Did the power go off at noon? A continuous voltage recorder showed normal voltage throughout noon. The outage alarm was traced to a loose alarm cable.","no"),
]
def trial(question):
    graph,tokens=b.predict("http://127.0.0.1:11434","qwen3:4b-instruct",PROMPT,question,max_tokens=200)
    evidence=[]
    items={}
    passage=question.partition("?")[2]
    for key in ("yes","no","invalid"):
        arr=graph.get(key)
        if not isinstance(arr,list):
            return dict(error="invalid array",tokens=tokens,raw=graph)
        for quote in arr:
            if not isinstance(quote,str) or not quote.strip() or quote not in passage:
                return dict(error="ungrounded quote",tokens=tokens,raw=graph)
            if key=="invalid":
                if quote not in items:
                    return dict(error="missing source",tokens=tokens,raw=graph)
                for idx in items[quote]:
                    evidence.append(Evidence("undercut",2,target=idx))
            else:
                evidence.append(Evidence(key,2))
                items.setdefault(quote,[]).append(len(evidence))
    return dict(answer=evaluate({1:evidence})[1].answer,flat=evaluate({1:evidence},recursive=False)[1].answer,tokens=tokens,raw=graph)
if __name__=="__main__":
    import sys
    rows=json.loads(Path(sys.argv[1]).read_text())["rows"]
    output=[]
    for suite,cases in [("previous",[(x['text'],x['expected']) for x in rows]),("new",NEW)]:
        for question,expected in cases:
            result=trial(question)
            row=dict(suite=suite,question=question,expected=expected,compact=result)
            if suite=="new":
                row["current"]=b.benchmark_rei("http://127.0.0.1:11434","qwen3:4b-instruct",[(question,expected)])["results"][0]
                row["single"],row["single_tokens"]=b.predict("http://127.0.0.1:11434","qwen3:4b-instruct",b.SINGLE_PASS,question)
            output.append(row)
    Path("rei_compact_results.json").write_text(json.dumps(output,indent=2))
