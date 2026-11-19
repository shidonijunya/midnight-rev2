"""Extract embedded JS from Python source to allow Node syntax checks in CI."""
import ast
import pathlib

root = pathlib.Path(__file__).resolve().parents[1]
for filename, variable, output in (
    ("tactical_map.py", "source", "/tmp/midnight-map.js"),
    ("dice3d.py", "JS", "/tmp/midnight-dice.js"),
):
    tree = ast.parse((root / filename).read_text(encoding="utf-8"))
    candidate = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == variable for t in node.targets
        ) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            candidate = node.value.value
            break
    if not candidate:
        raise SystemExit("Missing embedded JS: " + filename)
    if filename == "tactical_map.py":
        candidate = candidate.split("<script>", 1)[1].split("</script>", 1)[0]
        candidate = candidate.replace("__OPTIONS__", "{}")
    else:
        candidate = candidate.replace("__SPEC__", "{}").replace("__HEIGHT__", "250")
    pathlib.Path(output).write_text(candidate, encoding="utf-8")
