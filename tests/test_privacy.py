"""PII / log hygiene regression test (Phase 5G / spec sections 36-41)."""
import sys, os, io, logging, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# capture everything the pipeline logs during one run
buf = io.StringIO()
handler = logging.StreamHandler(buf)
root = logging.getLogger()
root.addHandler(handler)
root.setLevel(logging.INFO)

from tests.golden.fixtures import fixture_F_identity_protection
from pipeline.service import analyze
r, jd = fixture_F_identity_protection()
res = analyze(r, jd, mode="strict", job_id="pii_test")

root.removeHandler(handler)
logged = buf.getvalue()

pii_hits = []
if "Riley" in logged: pii_hits.append("name 'Riley'")
if "riley@example.com" in logged: pii_hits.append("email")
if re.search(r"\b555-0133\b", logged): pii_hits.append("phone")
if "BrandHouse Media" in logged: pii_hits.append("employer")

print(f"  log lines captured: {len(logged.splitlines())}")
print(f"  PII hits in operational logs: {pii_hits if pii_hits else 'NONE'}")

# secrets scan of the same output
secret_hits = [w for w in ("api_key", "password", "token=") if w in logged.lower()]
print(f"  secret markers: {secret_hits if secret_hits else 'NONE'}")

# rotation: handler exists with configured limits
from utils.logger import setup_logger
lg = setup_logger("rotation_check")
rot = [h for h in lg.handlers if hasattr(h, "maxBytes")]
print(f"  rotating handler present: {bool(rot)} (maxBytes={rot[0].maxBytes if rot else 'n/a'}, backupCount={rot[0].backupCount if rot else 'n/a'})")

ok = not pii_hits and not secret_hits and bool(rot)
print("PII hygiene:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)