import json
for s in ("status_quo","seattle","full_pbd"):
    m=json.load(open(f"C:/projects/philly-parking-benefit-districts/outputs/models/{s}/meta.json"))
    p=m.get("provenance",{})
    print(s,"top keys",list(m))
    print("  provenance keys",list(p))
    ss=p.get("segment_source")
    print("  segment_source:",json.dumps(ss)[:900])
    print("  commit",p.get("git_commit"),"dirty",p.get("git_dirty"),"ts",p.get("timestamp_utc"))
