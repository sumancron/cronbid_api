# utils/security.py

import bcrypt

def hash_password(password: str) -> str:
    # Hash a password for storing
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Verify a stored password against one provided by user
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
