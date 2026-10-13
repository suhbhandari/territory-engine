"""The two checks that read tone rather than citations.

Both exist because the citation and number checks are blind to them: the words are
lowercase and carry no number, so a guess written as a finding passed every check.
Word lists are vertical config, so the tests supply their own.
"""
from src.brief import forbidden_words, hedged_claims, smart_title

HEDGES = ["which suggests", "suggests", "likely", "appears to"]
CLAIMS = ["ongoing", "regularly", "sister", "common ownership"]


def test_guess_word_followed_by_a_frequency_claim_is_caught():
    text = "Runs its hiring through a job board, which suggests recruiting is ongoing."
    assert hedged_claims(text, HEDGES, CLAIMS) == ["'which suggests ... ongoing'"]


def test_guess_word_followed_by_an_ownership_claim_is_caught():
    text = "Two firms use one domain, which suggests common ownership."
    assert hedged_claims(text, HEDGES, CLAIMS) == ["'which suggests ... common ownership'"]


def test_stating_the_fact_without_the_guess_passes():
    assert hedged_claims("Runs its hiring through a job board.", HEDGES, CLAIMS) == []


def test_a_claim_word_with_no_guess_word_passes():
    # A fact may say something happens regularly; only a guessed one is rejected.
    assert hedged_claims("The filing is submitted regularly under the rules.", HEDGES, CLAIMS) == []


def test_a_guess_word_after_the_claim_word_is_not_a_match():
    # Order matters: the guess has to introduce the claim.
    assert hedged_claims("Filings are ongoing; the office appears to be open.", HEDGES, CLAIMS) == []


def test_the_two_are_judged_sentence_by_sentence():
    text = "It appears to be open. Filings are ongoing."
    assert hedged_claims(text, HEDGES, CLAIMS) == []


def test_no_word_lists_means_no_check():
    assert hedged_claims("which suggests it is ongoing", [], []) == []


def test_the_engines_own_words_are_caught_in_outreach():
    assert forbidden_words("You are one of six firms in my territory.", ["territory", "tier"]) == ["territory"]


def test_a_forbidden_word_inside_a_longer_word_is_not_a_match():
    assert forbidden_words("We work with care providers.", ["care"]) == ["care"]
    assert forbidden_words("Careful work.", ["care"]) == []


def test_capitals_are_title_cased_and_ordinals_kept_lowercase():
    assert smart_title("180 W 80TH ST") == "180 W 80th St"
    assert smart_title("1 E 3RD ST") == "1 E 3rd St"


def test_a_value_not_in_capitals_is_left_alone():
    assert smart_title("12 Mixed Case Rd") == "12 Mixed Case Rd"
    assert smart_title("") == ""
