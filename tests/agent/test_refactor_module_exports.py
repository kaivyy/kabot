from kabot.agent import skills, skills_matching
from kabot.agent.tools import stock, stock_matching


def test_skills_module_reexports_matching_helpers():
    assert skills.looks_like_skill_creation_request is skills_matching.looks_like_skill_creation_request
    assert skills.looks_like_skill_install_request is skills_matching.looks_like_skill_install_request
    assert skills.looks_like_skill_catalog_request is skills_matching.looks_like_skill_catalog_request
    assert skills.normalize_skill_reference_name is skills_matching.normalize_skill_reference_name


def test_stock_module_reexports_matching_helpers():
    assert stock.extract_stock_symbols is stock_matching.extract_stock_symbols
    assert stock.extract_stock_name_candidates is stock_matching.extract_stock_name_candidates
    assert stock.extract_crypto_ids is stock_matching.extract_crypto_ids
