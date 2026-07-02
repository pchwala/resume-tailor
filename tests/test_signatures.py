from tracker.signatures import signature


def test_case_and_whitespace_normalization():
    assert signature("Acme Corp", "Developer", "Warsaw") == signature(
        "  ACME   corp  ", "developer", "warsaw"
    )


def test_company_suffix_stripped():
    assert signature("Acme Inc.", "Developer", "") == signature("Acme", "Developer", "")


def test_chained_company_suffixes_stripped():
    assert signature("Acme Corp Ltd", "Developer", "") == signature(
        "Acme", "Developer", ""
    )


def test_suffix_like_substring_not_stripped():
    assert signature("Cisco", "Developer", "") != signature("Cis", "Developer", "")


def test_seniority_synonym_collapsed():
    assert signature("Acme", "Sr. Developer", "") == signature(
        "Acme", "Senior Developer", ""
    )
    assert signature("Acme", "Jr Developer", "") == signature(
        "Acme", "Junior Developer", ""
    )


def test_different_inputs_produce_different_signatures():
    base = signature("Acme", "Developer", "Warsaw")
    assert base != signature("Beta", "Developer", "Warsaw")
    assert base != signature("Acme", "Manager", "Warsaw")
    assert base != signature("Acme", "Developer", "Krakow")


def test_output_is_sha256_hex_digest():
    sig = signature("Acme", "Developer", "Warsaw")
    assert len(sig) == 64
    int(sig, 16)  # raises ValueError if not valid hex
