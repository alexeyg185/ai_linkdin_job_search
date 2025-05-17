"""
Security utility functions.
This module provides helper functions for security-related tasks.
"""

import re
import secrets
import string
import hashlib
import hmac
from typing import Optional, Tuple, Dict, Any
import urllib.parse
import html
from constants.security import SecurityConstants


def generate_secure_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.

    Args:
        length: Length of the token in bytes

    Returns:
        token: Secure random token as a hex string
    """
    return secrets.token_hex(length)


def generate_password(length: int = 12) -> str:
    """
    Generate a secure random password.

    Args:
        length: Length of the password

    Returns:
        password: Secure random password
    """
    alphabet = string.ascii_letters + string.digits + string.punctuation
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and sum(c.isdigit() for c in password) >= 3):
            break
    return password



def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a password against security requirements.

    Requirements:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character

    Args:
        password: Password to validate

    Returns:
        valid: True if password meets requirements, False otherwise
        message: Error message if invalid, None if valid
    """
    if len(password) < SecurityConstants.PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {SecurityConstants.PASSWORD_MIN_LENGTH} characters long"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"

    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"

    if not any(c in string.punctuation for c in password):
        return False, "Password must contain at least one special character"

    return True, None


def sanitize_input(text: str) -> str:
    """
    Sanitize user input to prevent XSS attacks.

    Args:
        text: Input text to sanitize

    Returns:
        sanitized: Sanitized text
    """
    # First do a regular escape
    escaped = html.escape(text, quote=True)

    return escaped


def validate_url(url: str) -> bool:
    """
    Validate a URL for security.

    Args:
        url: URL to validate

    Returns:
        valid: True if URL is valid and safe, False otherwise
    """
    # Parse the URL
    parsed = urllib.parse.urlparse(url)

    # Check if scheme is http or https
    if parsed.scheme not in ('http', 'https'):
        return False

    # Check if netloc is not empty (has domain)
    if not parsed.netloc:
        return False

    # Simple check for common URL pattern
    url_pattern = r'^(https?:\/\/)?(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'
    if not re.match(url_pattern, url):
        return False

    return True


def sign_data(data: str, secret: str) -> str:
    """
    Create a signature for data using HMAC-SHA256.

    Args:
        data: Data to sign
        secret: Secret key for signing

    Returns:
        signature: HMAC signature as hex string
    """
    return hmac.new(
        secret.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def verify_signature(data: str, signature: str, secret: str) -> bool:
    """
    Verify a signature for data using HMAC-SHA256.

    Args:
        data: Data that was signed
        signature: Signature to verify
        secret: Secret key used for signing

    Returns:
        valid: True if signature is valid, False otherwise
    """
    expected_signature = sign_data(data, secret)
    return hmac.compare_digest(signature, expected_signature)


def validate_json_input(data: Dict[str, Any], required_fields: list,
                        field_validators: Dict[str, callable] = None) -> Tuple[bool, Optional[str]]:
    """
    Validate JSON input data against required fields and field-specific validators.

    Args:
        data: Input data dictionary
        required_fields: List of required field names
        field_validators: Dictionary of field name to validator function

    Returns:
        valid: True if data is valid, False otherwise
        message: Error message if invalid, None if valid
    """
    # Check for required fields
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"

    # Apply field-specific validators if provided
    if field_validators:
        for field, validator in field_validators.items():
            if field in data:
                valid, message = validator(data[field])
                if not valid:
                    return False, f"Invalid {field}: {message}"

    return True, None