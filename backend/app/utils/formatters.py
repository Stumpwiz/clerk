import re

def format_phone(phone: str | None) -> str:
    """
    Format a 10-digit U.S. phone number as (NPA) NXX-XXXX.
    
    - Accepts an existing phone value.
    - Strips non-digits.
    - If exactly 10 digits remain, returns "(XXX) XXX-XXXX".
    - Otherwise returns the original value unchanged (or a safely trimmed version if appropriate).
    - Preserves existing behavior for blank/null phone numbers.
    """
    if not phone:
        return phone or ""
    
    # Strip all non-digit characters
    digits = re.sub(r"\D", "", phone)
    
    # Check if exactly 10 digits remain
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    
    return phone
