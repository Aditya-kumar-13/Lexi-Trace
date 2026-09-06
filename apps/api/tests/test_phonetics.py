from lexitrace.phonetics import indic_transliteration_similarity, transliteration_skeleton


def test_common_indic_romanization_choices_share_a_skeleton() -> None:
    assert transliteration_skeleton("Aadithya") == transliteration_skeleton("Aditya")
    assert transliteration_skeleton("Lakshmi") == transliteration_skeleton("Laxmi")
    assert indic_transliteration_similarity("Karthick", "Kartik") == 1.0


def test_nearby_distinct_names_remain_below_the_safe_development_boundary() -> None:
    assert indic_transliteration_similarity("Kiran", "Karan") < 0.91
    assert indic_transliteration_similarity("Siddharth", "Siddhant") < 0.91
    assert indic_transliteration_similarity("Rohit", "Mohit") < 0.91


def test_empty_or_non_latin_input_has_no_phonetic_similarity() -> None:
    assert indic_transliteration_similarity("", "Aditya") == 0.0
    assert indic_transliteration_similarity("आदित्य", "Aditya") == 0.0
