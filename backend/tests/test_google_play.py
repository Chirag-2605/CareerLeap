from app.google_play import PRODUCT_CREDITS, obfuscated_account_id


def test_google_play_credit_products_are_fixed():
    assert PRODUCT_CREDITS == {
        "careerleap_10_scans": 10,
        "careerleap_25_scans": 25,
    }


def test_obfuscated_account_id_is_stable_and_not_plain_uid():
    uid = "firebase-user-123"
    value = obfuscated_account_id(uid)

    assert value == obfuscated_account_id(uid)
    assert value != uid
    assert len(value) == 64
