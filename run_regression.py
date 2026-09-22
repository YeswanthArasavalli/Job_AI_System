"""Run all regression test suites and report pass/fail counts."""
import subprocess, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
tests = ['test_multi_role.py', 'test_behavior.py', 'test_quality_e2e.py']
all_pass = True
for t in tests:
    r = subprocess.run([sys.executable, t], capture_output=True, text=True, 
                       encoding='utf-8', errors='replace')
    # Look specifically for the test summary line "Passed: X | Failed: Y"
    found = False
    for line in (r.stdout + r.stderr).splitlines():
        if 'Passed:' in line and 'Failed:' in line:
            print(f"  {t}: {line.strip()}")
            if 'Failed: 0' not in line:
                all_pass = False
            found = True
            break
    if not found:
        if r.returncode != 0:
            print(f"  {t}: EXIT CODE {r.returncode}")
            all_pass = False
        else:
            print(f"  {t}: OK (exit 0)")
print(f"\n  {'ALL REGRESSIONS PASS' if all_pass else 'REGRESSION FAILURES'}")
