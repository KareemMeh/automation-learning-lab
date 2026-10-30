
from pwdlib import PasswordHash

# Create a reusable password hasher
hasher = PasswordHash.recommended()


# Convert a plain password into an Argon2 hash
def hash_password(password: str) -> str:
    return hasher.hash(password)


# Check a plain password against a stored hash
def verify_password(
    plain_password: str,
    stored_hash: str
) -> bool:
    return hasher.verify(plain_password, stored_hash)
