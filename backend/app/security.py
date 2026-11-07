import hashlib
import hmac
import os
import time

import jwt


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        salt, digest = stored.split("$")
        check = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1)
    except ValueError:
        return False
    return hmac.compare_digest(check.hex(), digest)


def make_token(secret, user_id, role, minutes):
    return jwt.encode({"sub": str(user_id), "role": role, "exp": int(time.time()) + minutes * 60}, secret, algorithm="HS256")


def read_token(secret, token):
    return jwt.decode(token, secret, algorithms=["HS256"])
