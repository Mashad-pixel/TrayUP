import base64
import hashlib
import hmac
import json
import urllib.parse
from typing import Any, Dict, Optional, Tuple

from app.services.errors import OrderError


def build_upi_intent_uri(
    vpa: str,
    merchant_name: str,
    amount_paise: int,
    order_number: str,
    note: Optional[str] = None,
) -> Dict[str, str]:
    """Build standard NPCI UPI payment intent URI and app-specific URIs.

    Format:
        upi://pay?pa={vpa}&pn={name}&am={amount}&cu=INR&tr={order_number}&tn={note}
    """
    if not vpa or "@" not in vpa:
        raise OrderError("INVALID_VPA", "A valid UPI VPA is required to generate payment links.", 400)
    if amount_paise <= 0:
        raise OrderError("INVALID_AMOUNT", "Amount must be greater than zero.", 400)

    amount_inr = f"{amount_paise / 100:.2f}"
    clean_note = note or f"Order {order_number}"

    params = {
        "pa": vpa.strip(),
        "pn": merchant_name.strip() or "Canteen",
        "am": amount_inr,
        "cu": "INR",
        "tr": str(order_number).strip(),
        "tn": clean_note,
    }
    query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)

    standard_uri = f"upi://pay?{query_string}"
    phonepe_uri = f"phonepe://pay?{query_string}"
    gpay_uri = f"gpay://upi/pay?{query_string}"
    paytm_uri = f"paytmmp://pay?{query_string}"

    return {
        "upi_uri": standard_uri,
        "phonepe_uri": phonepe_uri,
        "gpay_uri": gpay_uri,
        "paytm_uri": paytm_uri,
        "amount_paise": amount_paise,
        "amount_inr": amount_inr,
        "order_number": order_number,
    }


def render_upi_qr_svg(upi_uri: str) -> str:
    """Render a pure SVG string for the given UPI URI using qrcode."""
    if not upi_uri or not upi_uri.startswith(("upi://", "phonepe://", "https://")):
        raise OrderError("INVALID_URI", "Cannot generate QR for invalid URI.", 400)

    # Imported here, like presence_service.py, so importing the app never requires the package.
    import qrcode
    import qrcode.image.svg

    img = qrcode.make(
        upi_uri,
        image_factory=qrcode.image.svg.SvgPathImage,
        box_size=10,
        border=2,
    )
    svg_bytes = img.to_string()
    return svg_bytes.decode("utf-8")


def verify_phonepe_signature(
    response_base64: str,
    x_verify_header: str,
    salt_key: str,
    salt_index: str = "1",
) -> bool:
    """Verify PhonePe X-VERIFY header using SHA256(Base64_Response + SaltKey) + '###' + SaltIndex.

    Timing-attack resistant using hmac.compare_digest.
    """
    if not response_base64 or not x_verify_header or not salt_key:
        return False

    try:
        parts = x_verify_header.strip().split("###")
        if len(parts) != 2:
            return False
        received_hash, received_index = parts[0], parts[1]

        if str(received_index) != str(salt_index):
            return False

        to_hash = (response_base64.strip() + salt_key.strip()).encode("utf-8")
        expected_hash = hashlib.sha256(to_hash).hexdigest()

        return hmac.compare_digest(received_hash.lower(), expected_hash.lower())
    except Exception:
        return False


def decode_phonepe_callback(
    raw_body_bytes: bytes,
    x_verify_header: str,
    salt_key: str,
    salt_index: str = "1",
) -> Tuple[Dict[str, Any], str]:
    """Validate and decode a PhonePe server-to-server callback.

    Returns (payload_dict, raw_response_base64).
    Raises OrderError on verification failure or invalid payload.
    """
    if not raw_body_bytes:
        raise OrderError("EMPTY_PAYLOAD", "Empty webhook payload received.", 400)

    try:
        data = json.loads(raw_body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise OrderError("INVALID_JSON", "Callback body is not valid JSON.", 400) from exc

    if not isinstance(data, dict):
        raise OrderError("INVALID_JSON", "Callback body must be a JSON object.", 400)

    response_b64 = data.get("response")
    if not response_b64 or not isinstance(response_b64, str):
        raise OrderError("MISSING_RESPONSE", "PhonePe callback missing base64 response string.", 400)

    if not verify_phonepe_signature(response_b64, x_verify_header, salt_key, salt_index):
        raise OrderError("INVALID_SIGNATURE", "PhonePe X-VERIFY signature verification failed.", 400)

    try:
        decoded_bytes = base64.b64decode(response_b64)
        callback_dict = json.loads(decoded_bytes.decode("utf-8"))
    except Exception as exc:
        raise OrderError("INVALID_DECODED_DATA", "Could not decode PhonePe base64 payload.", 400) from exc

    return callback_dict, response_b64
