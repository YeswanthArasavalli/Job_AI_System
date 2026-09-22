"""Clean runner for test_execution_engine.py - filters out log noise"""
import subprocess, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
r = subprocess.run([sys.executable, 'test_execution_engine.py'],
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
for line in (r.stdout + r.stderr).splitlines():
    l = line.strip()
    skip = any(k in l for k in ['File "', 'Message:', 'Traceback', 'PermissionError',
                                 'os.rename', 'doRollover', 'handlers.py',
                                 'logging error', 'Call stack', 'Arguments:', '--- Log'])
    if not skip and len(l) > 2:
        print(l)
