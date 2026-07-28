import json

from scripts.generate_matching_review_queue import generate
from tests.test_matching_columnar import sample_entry


def test_cli_generation_matches_golden_queue(tmp_path):
    source = tmp_path / "entries.jsonl"
    source.write_text(
        sample_entry().model_dump_json() + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "output"
    generate(source, output)
    expected = __file__.replace("test_matching_review_queue_generation.py", "")
    golden = (
        __import__("pathlib").Path(expected)
        / "fixtures"
        / "matching"
        / "expected_review_queue.jsonl"
    )
    assert (output / "review_queue.jsonl").read_text(
        encoding="utf-8"
    ) == golden.read_text(encoding="utf-8")
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["candidate_count"] == 1
