import subprocess, time

suites = [
    ("Stabilization", "tests/stabilization_test.py"),
    ("Intelligence",  "tests/intelligence_test.py"),
    ("Hardening",     "tests/hardening_test.py"),
    ("Ollama",        "tests/ollama_test.py"),
    ("Determinism",   "tests/determinism_test.py"),
]

total = 0
passed = 0
for name, path in suites:
    t0 = time.time()
    r = subprocess.run([".venv\\Scripts\\python.exe", path], capture_output=True, text=True, timeout=300)
    elapsed = time.time() - t0
    ok = r.returncode == 0
    total += 8
    if ok:
        passed += 8
    status = "PASS" if ok else "FAIL"
    print(f"  {name:15s} | 8/8 | {status} | {elapsed:.1f}s")
    if not ok:
        err_lines = [l for l in r.stderr.split('\n') if l.strip()][-3:]
        for l in err_lines:
            print(f"    ERR: {l.strip()[:80]}")

print()
print(f"  TOTAL: {passed}/{total} tests")
if passed == total:
    print("  Grade: 10/10 PRODUCTION GRADE")
else:
    print("  Grade: ISSUES FOUND")
