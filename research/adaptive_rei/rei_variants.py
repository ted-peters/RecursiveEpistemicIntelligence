import json
from rei_measure import CASES, MODEL, URL, measure
import adaptive_rei_benchmark as b
changes=[
(1,"paraphrase","Was the mural finished by Friday? The artist appears in a photo of the completed work. A reset erased the camera's date setting, and the date of the shot cannot be recovered."),
(4,"paraphrase","Was tray R sterilized? The log credits R with completing the cycle. Staff later discovered the entry was duplicated from P. No one independently checked R."),
(9,"paraphrase","Did the new signs reduce queue times? Wait times fell after the new signs appeared. Staffing doubled at the same time, so the two effects cannot be distinguished."),
(0,"order","Was the mural finished by Friday? The invoice misspells the painter's name. A dated photograph from Thursday shows the completed mural."),
(12,"order","Did sample L pass inspection? An independent retest of L against the same criteria recorded a pass. A release notice uses sample M's chart by mistake."),
(16,"order","Did the runner finish? A clock error made her elapsed time unreliable. The finish judge saw her cross the line."),
]
out=[]
for i,kind,case in changes:
 expected=CASES[i][2]
 out.append(dict(case_index=i,change=kind,text=case,expected=expected,rei=measure(case,expected,"rei")))
open("/tmp/rei_variants.json","w").write(json.dumps(out,indent=2))
r=b.benchmark(URL,MODEL,[(c,e) for _,c,e in CASES])
open("/tmp/rei_review_modes.json","w").write(json.dumps(r,indent=2))
print(r["scores"])
