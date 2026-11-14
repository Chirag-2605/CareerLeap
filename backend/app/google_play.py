from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from fastapi import HTTPException

from .config import settings

GOOGLE_PLAY_SCOPE = "https://www.googleapis.com/auth/androidpublisher"
PRODUCT_CREDITS = {
    "careerleap_10_scans": 10,
    "careerleap_25_scans": 25,
}


def obfuscated_account_id(user_id: str) -> str:
    """Return a stable, non-reversible account identifier accepted by Play Billing."""
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()


def verify_product_purchase(product_id: str, purchase_token: str, user_id: str) -> Dict[str, Any]:
    """Verify a one-time product purchase with the current Google Play purchases v2 API."""
    if product_id not in PRODUCT_CREDITS:
        raise HTTPException(status_code=400, detail="Unknown Google Play credit product.")
    if not purchase_token or len(purchase_token) > 4096:
        raise HTTPException(status_code=400, detail="A valid Google Play purchase token is required.")
    if not settings.google_play_service_account_json:
        raise HTTPException(status_code=503, detail="Google Play purchase verification is not configured.")

    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account

        service_account_info = json.loads(settings.google_play_service_account_json)
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=[GOOGLE_PLAY_SCOPE],
        )
        session = AuthorizedSession(credentials)
        url = (
            "https://androidpublisher.googleapis.com/androidpublisher/v3/"
            "applications/{}/purchases/productsv2/tokens/{}"
        ).format(settings.google_play_package_name, purchase_token)
        response = session.get(url, timeout=12)
    except Exception:
        raise HTTPException(status_code=503, detail="Google Play verification is temporarily unavailable.")

    try:
        if response.status_code in (400, 404):
            raise HTTPException(status_code=400, detail="Google Play could not verify this purchase.")
        if response.status_code in (401, 403):
            raise HTTPException(status_code=503, detail="Google Play verification credentials need attention.")
        if response.status_code != 200:
            raise HTTPException(status_code=503, detail="Google Play verification is temporarily unavailable.")
        purchase = response.json()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Google Play returned an invalid verification response.")
    finally:
        try:
            response.close()
            session.close()
        except Exception:
            pass

    purchase_state = (purchase.get("purchaseStateContext") or {}).get("purchaseState")
    if purchase_state != "PURCHASED":
        raise HTTPException(status_code=409, detail="This Google Play purchase is not completed. Pending purchases cannot add credits.")

    line_items = purchase.get("productLineItem") or []
    if len(line_items) != 1 or line_items[0].get("productId") != product_id:
        raise HTTPException(status_code=400, detail="The purchased product does not match the selected credit pack.")

    offer_details = line_items[0].get("productOfferDetails") or {}
    if offer_details.get("consumptionState") != "CONSUMPTION_STATE_YET_TO_BE_CONSUMED":
        raise HTTPException(status_code=409, detail="This Google Play purchase has already been consumed.")
    if int(offer_details.get("quantity", 1)) != 1:
        raise HTTPException(status_code=400, detail="Bulk quantities are not supported for this credit pack.")

    expected_account_id = obfuscated_account_id(user_id)
    if purchase.get("obfuscatedExternalAccountId") != expected_account_id:
        raise HTTPException(status_code=403, detail="This purchase is not associated with the signed-in CareerLeap account.")

    return {
        "product_id": product_id,
        "credits": PRODUCT_CREDITS[product_id],
        "order_id": purchase.get("orderId"),
        "purchase_completion_time": purchase.get("purchaseCompletionTime"),
    }
