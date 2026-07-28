from tests.test_matching_columnar import sample_entry

from global_medicines_atlas.matching_columnar import write_matching_outputs


def test_end_to_end_output_never_promotes_a_candidate(tmp_path):
    write_matching_outputs([sample_entry()], tmp_path)
    queue = (tmp_path / "review_queue.jsonl").read_text(encoding="utf-8")
    assert '"review_state":"pending_review"' in queue
    assert '"clinical_equivalence_claim":false' in queue
