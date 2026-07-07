import ast

path = "arnold_pipelines/megaplan/semantic_health.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

tree = ast.parse(src)

# Find the _check_authority_records function and inspect its body
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "_check_authority_records":
        print(f"_check_authority_records spans lines {node.lineno}-{node.end_lineno}")
        for child in ast.iter_child_nodes(node):
            for sub in ast.walk(child):
                if hasattr(sub, "lineno") and 505 <= getattr(sub, "lineno", 0) <= 520:
                    print(f"  node@{sub.lineno}:{getattr(sub,'end_lineno','?')} {type(sub).__name__} {ast.dump(sub)[:160]}")
        # Print the try statement body
        for stmt in node.body:
            print(f"  STMT {type(stmt).__name__} @ line {stmt.lineno}")
            if isinstance(stmt, ast.Try):
                print("    TRY body:")
                for s in stmt.body:
                    print(f"      {type(s).__name__} @ {s.lineno}-{getattr(s,'end_lineno','?')} :: {ast.get_source_segment(src, s)[:120]!r}")
        break
