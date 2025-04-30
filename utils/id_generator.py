# utils/id_generator.py

from datetime import datetime
import random
import string

def generate_custom_id(prefix: str) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")[:-3]  # e.g., 20250429152030123
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix.upper()}_{timestamp}_{random_part}"
