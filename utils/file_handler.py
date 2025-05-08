import os
from pathlib import Path
import base64
from datetime import datetime

def save_brand_logo(brand_id: str, base64_image: str) -> str:
    """
    Save brand logo to filesystem and return the file path
    """
    # Create uploads directory if it doesn't exist
    upload_dir = Path("uploads/brand_logos")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Extract file extension from base64 header
    file_ext = base64_image.split(';')[0].split('/')[1]
    
    # Generate filename using brand_id and timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{brand_id}_{timestamp}.{file_ext}"
    
    # Full path for the file
    file_path = upload_dir / filename
    
    # Decode and save the image
    image_data = base64.b64decode(base64_image.split(',')[1])
    with open(file_path, 'wb') as f:
        f.write(image_data)
    
    return str(file_path)