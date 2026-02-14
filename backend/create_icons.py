#!/usr/bin/env python3
"""
Erstellt PWA Icons aus der SVG-Datei.
"""
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    import io
    import base64
    
    def create_icon(size):
        """Erstellt ein einfaches NZZ Icon."""
        img = Image.new('RGBA', (size, size), (26, 26, 26, 255))  # Dunkelgrauer Hintergrund
        draw = ImageDraw.Draw(img)
        
        # Text zeichnen
        try:
            # Versuche Systemschrift zu laden
            font_size = int(size * 0.4)
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", font_size)
        except:
            font = ImageFont.load_default()
        
        # NZZ Text
        text = "NZZ"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (size - text_width) // 2
        y = (size - text_height) // 2 - int(size * 0.1)
        
        draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)
        
        # Rote Linie
        line_y = y + text_height + int(size * 0.1)
        line_margin = int(size * 0.15)
        draw.rectangle([line_margin, line_y, size - line_margin, line_y + max(2, size // 64)], 
                       fill=(196, 30, 58, 255))
        
        return img
    
    # Icons erstellen
    base_dir = Path(__file__).parent.parent / 'frontend' / 'public'
    
    for size in [192, 512]:
        icon = create_icon(size)
        icon.save(base_dir / f'icon-{size}x{size}.png', 'PNG')
        print(f"✓ icon-{size}x{size}.png erstellt")
        
except ImportError:
    print("PIL nicht verfügbar, überspringe Icon-Erstellung")
    print("Die PWA funktioniert auch ohne Icons")
