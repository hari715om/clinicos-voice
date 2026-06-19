"""Quick test for parse_date_smart."""
import sys; sys.path.insert(0, r'C:\Projects\clinicos-voice\backend')
from app.agents.tool_definitions import parse_date_smart
from datetime import date

today = date.today().strftime('%Y-%m-%d')
tests = [
    ('25th June',    '2026-06-25'),
    ('19th June',    '2026-06-19'),
    ('June 19th',    '2026-06-19'),
    ('today',        today),
    ('2026-06-25',   '2026-06-25'),
    ('25 June 2026', '2026-06-25'),
]
all_ok = True
for inp, expected in tests:
    result = parse_date_smart(inp)
    ok = result == expected
    status = 'PASS' if ok else 'FAIL'
    print(f"  {status} | {inp!r:25} -> {result}  (expected {expected})")
    if not ok:
        all_ok = False

# Tomorrow test (dynamic)
result_tmr = parse_date_smart('tomorrow')
print(f"  {'PASS' if '-' in result_tmr else 'FAIL'} | 'tomorrow'             -> {result_tmr}")
print()
print('ALL PASS' if all_ok else 'SOME FAILURES')
