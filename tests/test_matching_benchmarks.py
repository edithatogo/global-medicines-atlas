import json
import sys

from benchmarks.benchmark_matching import benchmark
from scripts.benchmark_matching import main

from global_medicines_atlas.matching import MatchingRecord


def test_python_reference_benchmark_is_bounded():
    source = MatchingRecord(
        record_id="nz-1",
        jurisdiction="NZ",
        name="Paracetamol tablet",
        ingredients=("paracetamol",),
    )
    target = MatchingRecord(
        record_id="au-1",
        jurisdiction="AU",
        name="Paracetamol tablet",
        ingredients=("paracetamol",),
    )
    result = benchmark(source, (target,), iterations=2)
    assert result.engine == "python-reference"
    assert result.iterations == 2
    assert result.candidates == 2
    assert result.elapsed_seconds >= 0


def test_benchmark_cli_reports_python_reference(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["benchmark_matching.py", "--iterations", "1"],
    )
    main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["engine"] == "python-reference"
    assert payload["iterations"] == 1
