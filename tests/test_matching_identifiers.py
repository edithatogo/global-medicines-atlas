from global_medicines_atlas.matching_identifiers import shared_identifiers
from global_medicines_atlas.models import Identifier


def test_identifier_matching_is_normalized_and_deterministic() -> None:
    source = (
        Identifier(system="https://example.test/GTIN/", value=" 123 "),
        Identifier(system="urn:test", value="ABC"),
    )
    target = (
        Identifier(system="URN:TEST", value="abc"),
        Identifier(system="https://example.test/gtin", value="123"),
    )

    result = shared_identifiers(source, target)

    assert [(item.system, item.value) for item in result] == [
        ("https://example.test/gtin", "123"),
        ("urn:test", "abc"),
    ]


def test_unshared_identifiers_are_not_evidence() -> None:
    assert not shared_identifiers(
        (Identifier(system="urn:a", value="1"),),
        (Identifier(system="urn:a", value="2"),),
    )
