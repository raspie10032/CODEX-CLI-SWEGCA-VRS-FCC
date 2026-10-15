"""Checks captured request bodies against R1-R3 (design doc section 10.0).

usage: relsmoke_check.py <req-dir> <catalog.json> <slug> new|resume|custom [custom-file]
"""
import glob
import json
import re
import sys

E = [
    "When you run out of context, the conversation is automatically compacted into a summary, but you will still see all prior user requests.",
    "Compaction does not end the task.",
    "Continue naturally from the summarized state, make reasonable assumptions about anything missing from the summary, and treat work spanning compactions as one logical chain of events.",
    "Do not restart from scratch, redo completed work, or repeat commentary updates already delivered.",
    "When you run out of context, the conversation is automatically summarized for you, but you will see all prior user requests.",
    "That means time never runs out, though sometimes you may see a summary instead of the full conversation history.",
    "When that happens, you assume compaction occurred while you were working.",
    "Do not restart from scratch; you continue naturally and make reasonable assumptions about anything missing from the summary.",
    "Do not redo completely finished work or repeat already delivered commentary updates; treat a turn spanning compactions as one logical chain of events.",
    "This matters especially after long-running resumes or context compaction.",
    "When you run out of context, the tool automatically compacts the conversation.",
    "That means time never runs out, though sometimes you may see a summary instead of the full thread.",
]
MARK = re.compile(
    r"\bcompact(ion|ions|ed|s)\b|run out of context|summary instead of the full|restart from scratch",
    re.I,
)

req_dir, catalog_path, slug, mode = sys.argv[1:5]
bodies = [json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(f"{req_dir}/req-*.json"))]
def instructions_of(body):
    # This build sends base instructions as the first developer message of `input`.
    if isinstance(body.get("instructions"), str):
        return body["instructions"]
    for item in body.get("input", []):
        if item.get("type") == "message" and item.get("role") == "developer":
            text = "".join(x.get("text") or "" for x in item.get("content") or [])
            if text:
                return text
    return None


main = [dict(b, instructions=instructions_of(b)) for b in bodies if b.get("model") == slug]
main = [b for b in main if b["instructions"]]
print(f"requests={len(bodies)} main({slug})={len(main)}")
ok = bool(main)
template = next(
    m["model_messages"]["instructions_template"]
    for m in json.load(open(catalog_path, encoding="utf-8"))["models"]
    if m["slug"] == slug
)
template_e = sum(template.count(s) for s in E)
print(f"template E sentences={template_e}")
for i, body in enumerate(main):
    text = body["instructions"]
    e_hits = sum(text.count(s) for s in E)
    markers = len(MARK.findall(text))
    if mode == "custom":
        custom = open(sys.argv[5], encoding="utf-8").read()
        same = custom.strip() in text
        print(f"[{i}] custom verbatim={same} E={e_hits}")
        ok &= same and e_hits > 0
        continue
    clean = [p for p in re.split(r"\n{2,}", template) if not MARK.search(p)]
    missing = [p for p in clean if p not in text]
    print(f"[{i}] len={len(text)} E={e_hits} markers={markers} clean_paragraphs={len(clean)} missing={len(missing)}")
    ok &= e_hits == 0 and markers == 0 and not missing
    for p in missing[:3]:
        print("   missing:", p[:160].replace("\n", " "))
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
