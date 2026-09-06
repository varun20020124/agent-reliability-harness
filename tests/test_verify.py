from agent.verify import execute, results_match, verify

DB = "concert_singer"


def test_identical_query_matches():
    v = verify(DB, "SELECT count(*) FROM singer",
                   "SELECT count(*) FROM singer")
    assert v["correct"]


def test_column_order_does_not_matter():
    v = verify(DB, "SELECT name, country FROM singer",
                   "SELECT country, name FROM singer")
    assert v["correct"]


def test_wrong_result_fails():
    v = verify(DB, "SELECT count(*) FROM singer",
                   "SELECT count(*) FROM stadium")
    assert not v["correct"]


def test_syntax_error_fails_without_raising():
    v = verify(DB, "SELECT count(*) FROM singer", "SELEKT * FRM singer")
    assert not v["correct"]
    assert v["reason"] == "candidate error"


def test_row_order_ignored_when_gold_has_no_order_by():
    v = verify(DB, "SELECT name FROM singer",
                   "SELECT name FROM singer ORDER BY name DESC")
    assert v["correct"]


def test_row_order_enforced_when_gold_has_order_by():
    v = verify(DB, "SELECT name FROM singer ORDER BY age ASC",
                   "SELECT name FROM singer ORDER BY age DESC")
    assert not v["correct"]


def test_duplicates_are_not_collapsed():
    v = verify(DB, "SELECT country FROM singer",
                   "SELECT DISTINCT country FROM singer")
    assert not v["correct"]


def test_readonly_prevents_writes():
    r = execute(DB, "DROP TABLE singer")
    assert not r.ok

def test_numeric_string_matches_number():
    """Gold returns text '9'; a CAST version returns int 9. Same answer."""
    v = verify("dog_kennels",
               "SELECT max(age) FROM Dogs",
               "SELECT max(CAST(age AS INTEGER)) FROM Dogs")
    assert v["correct"]