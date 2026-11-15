"""Web Push (RFC 8030/8291) + VAPID (RFC 8292) usando solo `cryptography`."""
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def b64e(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64d(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _pub_bytes(pub):
    return pub.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def load_or_create_key(path):
    if os.path.exists(path):
        return serialization.load_pem_private_key(open(path, "rb").read(), None)
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    return key


def public_key_b64(key):
    return b64e(_pub_bytes(key.public_key()))


def encrypt(payload: bytes, p256dh: str, auth: str) -> bytes:
    ua_pub_b = b64d(p256dh)
    ua_pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_pub_b)
    as_key = ec.generate_private_key(ec.SECP256R1())
    as_pub_b = _pub_bytes(as_key.public_key())
    secret = as_key.exchange(ec.ECDH(), ua_pub)
    ikm = HKDF(hashes.SHA256(), 32, b64d(auth), b"WebPush: info\0" + ua_pub_b + as_pub_b).derive(secret)
    salt = os.urandom(16)
    cek = HKDF(hashes.SHA256(), 16, salt, b"Content-Encoding: aes128gcm\0").derive(ikm)
    nonce = HKDF(hashes.SHA256(), 12, salt, b"Content-Encoding: nonce\0").derive(ikm)
    ct = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    return salt + (4096).to_bytes(4, "big") + bytes([len(as_pub_b)]) + as_pub_b + ct


def vapid_header(key, endpoint, subject):
    u = urllib.parse.urlparse(endpoint)
    claims = {"aud": f"{u.scheme}://{u.netloc}", "exp": int(time.time()) + 12 * 3600, "sub": subject}
    signing = b64e(json.dumps({"typ": "JWT", "alg": "ES256"}).encode()) + "." + b64e(json.dumps(claims).encode())
    r, s = decode_dss_signature(key.sign(signing.encode(), ec.ECDSA(hashes.SHA256())))
    jwt = signing + "." + b64e(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return f"vapid t={jwt}, k={public_key_b64(key)}"


def send_push(key, subject, sub, payload: dict):
    """Devuelve 'ok', 'gone' (suscripción muerta, borrarla) o un texto de error."""
    body = encrypt(json.dumps(payload).encode(), sub["p256dh"], sub["auth"])
    req = urllib.request.Request(
        sub["endpoint"], data=body, method="POST",
        headers={
            "Authorization": vapid_header(key, sub["endpoint"], subject),
            "Content-Encoding": "aes128gcm",
            "Content-Type": "application/octet-stream",
            "TTL": "86400",
            "Urgency": "high",
        },
    )
    try:
        urllib.request.urlopen(req, timeout=15).read()
        return "ok"
    except urllib.error.HTTPError as e:
        return "gone" if e.code in (404, 410) else f"HTTP {e.code}"
    except Exception as e:
        return str(e)
