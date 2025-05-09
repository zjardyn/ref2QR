import io
import base64
import os
import qrcode
from PIL import Image
from flask import current_app

def generate_qr_data_url(data_url: str) -> str:
    """Generate a Base64-encoded PNG data URL for a QR code with logo overlay."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert('RGBA')
    try:
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../logo.png')
        logo = Image.open(logo_path).convert('RGBA')

        width, height = img.size
        logo_size = int(width * 0.25)
        logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
        pos = ((width - logo_size) // 2, (height - logo_size) // 2)
        mask = logo.split()[3] if len(logo.split()) == 4 else None
        img.paste(logo, pos, mask)
    except Exception as e:
        current_app.logger.error(f"Error adding logo to QR code: {e}")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{img_str}"