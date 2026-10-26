"""Static Snowflake dialect check. This is not a Snowflake server execution test."""

import ast, json, re, sys
from pathlib import Path
import sqlglot

ROOT = Path(__file__).resolve().parents[1]
files = [ROOT / "bird_strikes/snowflake_loader.py", ROOT / "scripts/build_snowflake.py"]
statements = (ROOT / "snowflake/setup.sql").read_text().split(";")
for file in files:
    tree = ast.parse(file.read_text())
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            statements.append(node.args[0].value.replace("%s", "'test'"))
checked = 0
unsupported = []
for sql in statements:
    if sql.strip():
        trees = sqlglot.parse(
            sql, read="snowflake", error_level=sqlglot.ErrorLevel.RAISE
        )
        if any(isinstance(t, sqlglot.exp.Command) for t in trees):
            unsupported.append(sql)
        else:
            checked += 1
print(
    f"Parsed {checked} SQL statements in the Snowflake dialect; {len(unsupported)} command(s) require server validation."
)
print("Not validated by parser:", unsupported)
print("No live account execution performed.")
