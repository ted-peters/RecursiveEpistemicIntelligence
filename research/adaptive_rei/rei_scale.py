import json,statistics,time
from adaptive_rei_engine import Evidence,evaluate
rows=[]
for shape in ("chain","shared premise"):
 for n in (2,8,32,64,128,256,512,1024):
    claims={1:(Evidence("no",3),)}
    for i in range(2,n+1):
        parent=(i-1 if shape=="chain" else 1)
        claims[i]=(Evidence("yes",2,((parent,"yes"),)),)
    row={"shape":shape,"claims":n}
    for mode in ("flat","recursive"):
        times=[]
        try:
            for _ in range(11):
                start=time.perf_counter_ns()
                d=evaluate(claims,recursive=mode=="recursive")[n]
                times.append((time.perf_counter_ns()-start)/1e6)
            row[mode]={"answer":d.answer,"median_ms":round(statistics.median(times),3)}
        except RecursionError:
            row[mode]={"error":"RecursionError"}
    rows.append(row)
open("/tmp/rei_scale.json","w").write(json.dumps(rows,indent=2))
print(rows)
