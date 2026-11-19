"""Run beside adaptive_rei_benchmark.py, with Ollama serving the installed model."""
import hashlib
import json
import statistics
import time
from pathlib import Path
import adaptive_rei_benchmark as b

CASES = [
("record valid","Was the mural finished by Friday? A dated photograph from Thursday shows the completed mural. The invoice misspells the painter's name.","yes"),
("record invalid","Was the mural finished by Friday? A photograph shows the completed mural. Its supposed Thursday date came from a camera whose clock had reset. Nobody recorded when it was taken.","uncertain"),
("observed absence","Was the loading bay vacant at noon? At noon an observer counted three vans inside the bay.","no"),
("observation","Was the loading bay vacant at noon? Continuous footage shows the entire bay empty throughout noon.","yes"),
("wrong subject","Was tray R sterilized? The ledger marks tray R complete. A clerk transcribed that mark from tray P's card by mistake. Nothing else documents tray R.","uncertain"),
("independent negative","Was tray R sterilized? The ledger marks tray R complete using tray P's card. An independent inspector observed tray R bypass the sterilizer and documented that it never entered one.","no"),
("independent positive","Was tray R sterilized? The ledger entry originated on another tray's card. A separate inspector watched tray R complete the full sterilization cycle.","yes"),
("stale record","Was bus 14 late on Wednesday? A dispatch note labels it late. The entry was carried over from Tuesday. No Wednesday arrival time was kept.","uncertain"),
("fresh negative","Was bus 14 late on Wednesday? Tuesday's dispatch note calls it late. On Wednesday the driver clocked in at the terminus exactly on schedule.","no"),
("causal ambiguity","Did the new signs reduce queue times? Queues shortened after the signs went up. A second service desk opened the same morning. The observations do not separate their effects.","uncertain"),
("conflicting reports","Did the bell ring at nine? Two equally credible listeners stood beside the bell. One heard it ring at nine and the other insists it stayed silent. There is no recording.","uncertain"),
("broken chain","Did sample L pass inspection? A release notice certifies a pass. Its approval was derived entirely from a technician's chart. An audit traced that chart to sample M. No other test exists for L.","uncertain"),
("chain with independent evidence","Did sample L pass inspection? A release notice uses sample M's chart by mistake. An independent retest of L against the same criteria recorded a pass.","yes"),
("negated action","Was the garden gate closed when Mia arrived? Mia walked through the open gate without touching it.","no"),
("time change","Was the projector on at ten? At nine the room checklist listed it as off. Video recorded the projector displaying slides at ten.","yes"),
("negative correction","Did the press stop during the shift? An alarm suggested a stoppage. A continuous shaft-speed trace later showed uninterrupted rotation for the whole shift.","no"),
("unrelated flaw","Did the runner finish? The finish judge saw her cross the line. A clock error made her elapsed time unreliable.","yes"),
("same subject negative","Did the archive contain folder D? The archivist checked every shelf and found folder D absent. The neighboring archive had a folder with the same name.","no"),
]
MODEL="qwen3:4b-instruct"
URL="http://127.0.0.1:11434"
def measure(case, expected, mode):
    before=time.perf_counter()
    if mode=="rei":
        data=b.benchmark_rei(URL,MODEL,[(case,expected)])
        row=data["results"][0]
    else:
        answer,tokens=b.predict(URL,MODEL,{"direct":b.BASELINE,"single":b.SINGLE_PASS}[mode],case)
        row={"answer":answer.get("answer"),"tokens":tokens}
    row["seconds"]=round(time.perf_counter()-before,4)
    return row

def main():
    paths=[Path(b.__file__),Path(b.__file__).with_name("adaptive_rei_engine.py")]
    report={"model":MODEL,"sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},"rows":[],"repeat":[]}
    modes=["direct","single","rei"]
    for i,(group,case,expected) in enumerate(CASES):
        row=dict(group=group,text=case,expected=expected)
        for mode in modes[i%3:]+modes[:i%3]:
            row[mode]=measure(case,expected,mode)
        report["rows"].append(row)
        print(i+1,flush=True)
    for idx in (0,4,11):
        _,case,expected=CASES[idx]
        report["repeat"].append({"case_index":idx,"rei":measure(case,expected,"rei")})
    Path("rei_measurements.json").write_text(json.dumps(report,indent=2))
if __name__=="__main__":
    main()
