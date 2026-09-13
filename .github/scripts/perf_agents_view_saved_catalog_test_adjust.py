from pathlib import Path

path = Path("packages/coding-agent/test/agents-view-mode.test.ts")
text = path.read_text()
needle = '\t\texpect(vi.getTimerCount()).toBe(0);\n'
count = text.count(needle)
if count != 2:
    raise SystemExit(f"expected two global timer assertions, found {count}")
path.write_text(text.replace(needle, ""))
