import hashlib
import secrets

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher(type=Type.ID)

MIN_LEN = 10
# Readable temporary password (no 0/O/1/l confusion). Shown to the admin once.
_ALPHABET = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def hash_password(p):
    return _hasher.hash(p)


def verify(h, p):
    try:
        return _hasher.verify(h, p)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def temp_password(n=12):
    return ''.join(_ALPHABET[b % len(_ALPHABET)] for b in secrets.token_bytes(n))


def sha256(s):
    return hashlib.sha256(s.encode()).hexdigest()


def password_problem(p):
    if not isinstance(p, str) or len(p) < MIN_LEN:
        return f'Use at least {MIN_LEN} characters.'
    if len(p) > 200:
        return 'That password is too long.'
    return ''
