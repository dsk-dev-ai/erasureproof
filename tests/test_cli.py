from __future__ import annotations

import json

from erasureproof.cli import main


def test_demo_json_output_is_machine_readable(tmp_path, capsys) -> None:
    code = main(["demo", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 0
    assert payload["status"] == "COMPLETE"
    assert payload["plan"]["steps"]
    assert payload["graph"]["nodes"]

    result_path = tmp_path / "result.json"
    result_path.write_text(captured.out, encoding="utf-8")
    assert main(["graph", str(result_path), "--format", "json"]) == 0
    graph = json.loads(capsys.readouterr().out)
    assert graph["nodes"]
    assert any(node["category"] for node in graph["nodes"])
    assert any(
        node["operation"] == "DELETE_RECORD" and node["category"]
        for node in graph["nodes"]
    )
