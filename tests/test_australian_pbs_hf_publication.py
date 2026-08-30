"""Hosted-only Australian PBS source-archive publication contract."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = PROJECT_ROOT / ".github/workflows/australian-pbs-hf-publication.yml"


def test_pbs_publication_is_exact_actions_only_and_public_from_outset() -> None:
    text = WORKFLOW.read_text()

    assert "exact_contract_commit:" in text
    assert 'test "${GITHUB_SHA}" = "${REQUESTED_COMMIT}"' in text
    assert 'test "${GITHUB_SHA}" = "${default_head}"' in text
    assert "environment: australian-pbs-publication" in text
    assert (
        "https://www.pbs.gov.au/publication/schedule/2026/04/2026-04-01-XML-V3.zip?variant=3"
        in text
    )
    assert "edithatogo/australian-pbs-source-archive" in text
    assert (
        "create_repo(repo_id=dataset, repo_type='dataset', private=False"
        in text
    )
    assert "private=True" not in text
    assert "delete_patterns=['*']" in text
    assert "token=False" in text
    assert "decision-0009" in text
    assert "scripts/qualify_pbs_v3_archive.py" in text
    assert "--http-metadata work/http-metadata.json" in text
    assert "--retrieved-at" in text
    assert "global-medicines-atlas.hosted-retrieval-attempt" in text
    assert "'status': 'succeeded'" in text
    assert "--body-file work/retrieval-attempt.json" in text
    assert "manifest['source_receipt']" in text
    assert "manifest['admission']" in text
    assert "rollback=restore-private-on-failure" not in text
    assert "visibility=public-from-outset" in text


def test_pbs_publication_verifies_before_cleanup() -> None:
    text = WORKFLOW.read_text()

    verify = text.index("Verify exact public revision anonymously")
    cleanup = text.index("Remove hosted temporary source bytes")
    receipt = text.index("Retain hosted qualification and cleanup receipt")
    assert verify < cleanup < receipt
    assert "rm -rf work/source.zip work/stage" in text[cleanup:receipt]
    assert "temporary_source_bytes_removed'] = True" in text[cleanup:receipt]
    assert "if: always()" not in text[cleanup:]
    assert "anonymous digest mismatch" in text[verify:cleanup]
    assert "gh issue comment 340" in text
