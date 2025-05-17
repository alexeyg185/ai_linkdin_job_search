import unittest
from unittest.mock import patch, MagicMock
import datetime
import json
import re
import hmac
import hashlib

from utils.formatters import (
    format_datetime, format_relative_time, format_currency,
    truncate_text, format_file_size, sanitize_html, format_json,
    format_linkedin_description
)
from utils.security import (
    generate_secure_token, generate_password, validate_password,
    sanitize_input, validate_url, sign_data, verify_signature,
    validate_json_input
)


class TestFormatters(unittest.TestCase):
    """Test cases for formatter utility functions."""

    def test_format_datetime(self):
        """Test formatting datetime objects and strings."""
        # Test with datetime object
        dt = datetime.datetime(2023, 1, 15, 14, 30, 45)
        formatted = format_datetime(dt)
        self.assertEqual(formatted, "2023-01-15 14:30:45")

        # Test with custom format
        formatted = format_datetime(dt, "%Y/%m/%d")
        self.assertEqual(formatted, "2023/01/15")

        # Test with ISO string
        formatted = format_datetime("2023-01-15T14:30:45")
        self.assertEqual(formatted, "2023-01-15 14:30:45")

        # Test with None
        formatted = format_datetime(None)
        self.assertEqual(formatted, "N/A")

        # Test with invalid string (should return as is)
        formatted = format_datetime("not a date")
        self.assertEqual(formatted, "not a date")

    def test_format_relative_time(self):
        """Test formatting relative time strings."""
        # Mock current time
        now = datetime.datetime(2023, 1, 15, 14, 30, 0)

        with patch('utils.formatters.datetime') as mock_datetime:
            mock_datetime.datetime.now.return_value = now
            # Properly pass methods through to avoid AttributeError
            mock_datetime.datetime.fromisoformat = datetime.datetime.fromisoformat
            mock_datetime.datetime.strptime = datetime.datetime.strptime

            # Test just now
            dt = now - datetime.timedelta(seconds=30)
            formatted = format_relative_time(dt)
            self.assertEqual(formatted, "just now")

            # Test minutes
            dt = now - datetime.timedelta(minutes=5)
            formatted = format_relative_time(dt)
            self.assertEqual(formatted, "5 minutes ago")

            # Test singular minute
            dt = now - datetime.timedelta(minutes=1)
            formatted = format_relative_time(dt)
            self.assertEqual(formatted, "1 minute ago")

            # Test hours
            dt = now - datetime.timedelta(hours=3)
            formatted = format_relative_time(dt)
            self.assertEqual(formatted, "3 hours ago")

            # Test days
            dt = now - datetime.timedelta(days=2)
            formatted = format_relative_time(dt)
            self.assertEqual(formatted, "2 days ago")

            # Test weeks
            dt = now - datetime.timedelta(days=14)
            formatted = format_relative_time(dt)
            self.assertEqual(formatted, "2 weeks ago")

            # Test months (format as date)
            dt = now - datetime.timedelta(days=60)
            formatted = format_relative_time(dt)
            self.assertEqual(formatted, "2023-01-15")  # Uses format_datetime for long periods

            # Test with None
            formatted = format_relative_time(None)
            self.assertEqual(formatted, "N/A")

            # Test with ISO string
            dt_str = (now - datetime.timedelta(hours=5)).isoformat()
            formatted = format_relative_time(dt_str)
            self.assertEqual(formatted, "5 hours ago")

    def test_format_currency(self):
        """Test formatting currency values."""
        # Basic test with default parameters
        formatted = format_currency(1234.56)
        self.assertTrue(formatted.startswith("$"))
        self.assertTrue("1,234.56" in formatted or "1234.56" in formatted)  # Account for locale differences

        # Test with different currency
        formatted = format_currency(1234.56, "EUR")
        self.assertTrue(formatted.startswith("€"))

        # Test with no decimals (JPY)
        formatted = format_currency(1234, "JPY")
        self.assertTrue(formatted.startswith("¥"))
        self.assertNotIn(".", formatted)  # JPY doesn't use decimal places

    def test_truncate_text(self):
        """Test truncating text to a maximum length."""
        # Test text that's already short enough
        short_text = "This is short"
        truncated = truncate_text(short_text, 20)
        self.assertEqual(truncated, short_text)

        # Test truncating long text
        long_text = "This is a very long text that needs to be truncated to a reasonable length"
        truncated = truncate_text(long_text, 20)
        self.assertTrue(len(truncated) <= 23)  # 20 + length of suffix
        self.assertTrue(truncated.endswith("..."))

        # Test with custom suffix
        truncated = truncate_text(long_text, 20, " (more)")
        self.assertTrue(truncated.endswith(" (more)"))

        # Test with empty text
        truncated = truncate_text("", 20)
        self.assertEqual(truncated, "")

        # Test with None
        truncated = truncate_text(None, 20)
        self.assertEqual(truncated, "")

    def test_format_file_size(self):
        """Test formatting file sizes in human-readable format."""
        # Test bytes
        formatted = format_file_size(500)
        self.assertEqual(formatted, "500 B")

        # Test kilobytes
        formatted = format_file_size(1500)
        self.assertEqual(formatted, "1.46 KB")

        # Test megabytes
        formatted = format_file_size(1500000)
        self.assertEqual(formatted, "1.43 MB")

        # Test gigabytes
        formatted = format_file_size(1500000000)
        self.assertEqual(formatted, "1.40 GB")

        # Test terabytes
        formatted = format_file_size(1500000000000)
        self.assertEqual(formatted, "1.36 TB")

    @patch('utils.formatters.BeautifulSoup')
    def test_sanitize_html(self, mock_bs):
        """Test sanitizing HTML content."""
        # Setup mock
        mock_soup = MagicMock()
        mock_bs.return_value = mock_soup
        mock_soup.find_all.side_effect = [
            # First call returns all tags
            [MagicMock(name='p'), MagicMock(name='script')],
            # Second call returns remaining tags after filtering
            [MagicMock(name='p')]
        ]
        mock_soup.__str__.return_value = "<p>Safe content</p>"

        # Call the function
        result = sanitize_html("<p>Test</p><script>alert('xss')</script>")

        # Verify BeautifulSoup was called
        mock_bs.assert_called_once()

        # Verify tags were checked and filtered
        mock_soup.find_all.assert_any_call(True)

        # Verify result
        self.assertEqual(result, "<p>Safe content</p>")

    def test_format_json(self):
        """Test formatting JSON data."""
        # Test with dictionary
        data = {"name": "John", "age": 30, "skills": ["Python", "SQL"]}
        formatted = format_json(data)

        # Verify JSON is properly formatted with indentation
        self.assertIn('"name": "John"', formatted)
        self.assertIn('"skills": [', formatted)

        # Test with JSON string
        json_str = '{"name":"John","age":30}'
        formatted = format_json(json_str)

        # Verify string was parsed and formatted
        self.assertIn('"name": "John"', formatted)
        self.assertIn('"age": 30', formatted)

        # Test with custom indent
        formatted = format_json(data, indent=4)

        # Verify indentation was applied
        self.assertTrue(any(line.startswith('    "') for line in formatted.split('\n')))

        # Test with invalid JSON string (should return as is)
        invalid_json = "not json"
        formatted = format_json(invalid_json)
        self.assertEqual(formatted, "not json")

    @patch('utils.formatters.BeautifulSoup')
    def test_format_linkedin_description(self, mock_bs):
        """Test formatting LinkedIn job descriptions."""
        # Setup mock
        mock_soup = MagicMock()
        mock_bs.return_value = mock_soup

        # Configure mock to simulate BeautifulSoup's behavior
        mock_script = MagicMock()
        mock_soup.find_all.return_value = [mock_script]
        mock_soup.get_text.return_value = "Job Description\n  Requirements  \n\nQualifications"

        # Call the function
        result = format_linkedin_description(
            "<div>Job Description<script>alert('xss')</script><br>Requirements<br><br>Qualifications</div>")

        # Verify BeautifulSoup was called
        mock_bs.assert_called_once()

        # Verify scripts were removed
        mock_script.extract.assert_called_once()

        # Verify result contains formatted text
        self.assertIn("Job Description", result)
        self.assertIn("<br>", result)


class TestSecurity(unittest.TestCase):
    """Test cases for security utility functions."""

    @patch('utils.security.secrets')
    def test_generate_secure_token(self, mock_secrets):
        """Test generating a secure random token."""
        # Setup mock
        mock_secrets.token_hex.return_value = "abcdef1234567890"

        # Call the function
        token = generate_secure_token()

        # Verify secrets.token_hex was called
        mock_secrets.token_hex.assert_called_once_with(32)

        # Verify result
        self.assertEqual(token, "abcdef1234567890")

        # Test with custom length
        mock_secrets.token_hex.reset_mock()
        generate_secure_token(16)
        mock_secrets.token_hex.assert_called_once_with(16)

    @patch('utils.security.secrets')
    def test_generate_password(self, mock_secrets):
        """Test generating a secure random password."""
        # Setup mock for a valid password
        mock_secrets.choice.side_effect = ['A', 'b', 'c', '1', '2', '3', '!', 'd', 'e', 'f', 'g', 'h']

        # Call the function
        password = generate_password()

        # Verify result
        self.assertEqual(password, "Abc123!defgh")
        self.assertEqual(len(password), 12)  # Default length

        # Test with custom length
        mock_secrets.choice.reset_mock()
        mock_secrets.choice.side_effect = ['A', 'b', 'c', '1', '2', '3', '!', 'd']
        password = generate_password(8)
        self.assertEqual(len(password), 8)

    def test_validate_password(self):
        """Test validating passwords against security requirements."""
        # Test valid password
        valid, message = validate_password("Abcdef1!")
        self.assertTrue(valid)
        self.assertIsNone(message)

        # Test too short
        valid, message = validate_password("Abc1!")
        self.assertFalse(valid)
        self.assertIn("at least 8 characters", message)

        # Test no uppercase
        valid, message = validate_password("abcdef1!")
        self.assertFalse(valid)
        self.assertIn("uppercase", message)

        # Test no lowercase
        valid, message = validate_password("ABCDEF1!")
        self.assertFalse(valid)
        self.assertIn("lowercase", message)

        # Test no digits
        valid, message = validate_password("Abcdefg!")
        self.assertFalse(valid)
        self.assertIn("digit", message)

        # Test no special characters
        valid, message = validate_password("Abcdef12")
        self.assertFalse(valid)
        self.assertIn("special character", message)

    def test_sanitize_input(self):
        """Test sanitizing user input."""
        # Test basic HTML escaping
        sanitized = sanitize_input("<script>alert('xss')</script>")
        self.assertEqual(sanitized, "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;")

        # Test with special characters
        sanitized = sanitize_input("John & Jane's <Company>")
        self.assertEqual(sanitized, "John &amp; Jane&#x27;s &lt;Company&gt;")

    def test_validate_url(self):
        """Test validating URLs for security."""
        # Test valid HTTP URLs
        self.assertTrue(validate_url("http://example.com"))
        self.assertTrue(validate_url("https://example.com/path?query=value"))
        self.assertTrue(validate_url("https://sub.example.co.uk"))

        # Test invalid URLs
        self.assertFalse(validate_url("ftp://example.com"))  # Wrong scheme
        self.assertFalse(validate_url("http://"))  # No domain
        self.assertFalse(validate_url("example.com"))  # No scheme
        self.assertFalse(validate_url("javascript:alert(1)"))  # JavaScript scheme

    def test_sign_data(self):
        """Test creating a signature for data."""
        # Test with simple data
        data = "test data"
        secret = "secret key"
        signature = sign_data(data, secret)

        # Verify signature format
        self.assertTrue(re.match(r'^[0-9a-f]{64}$', signature))  # 64 hex chars for SHA-256

        # Verify signature is deterministic
        signature2 = sign_data(data, secret)
        self.assertEqual(signature, signature2)

        # Verify different data produces different signatures
        different_signature = sign_data("different data", secret)
        self.assertNotEqual(signature, different_signature)

    def test_verify_signature(self):
        """Test verifying a signature."""
        # Create a signature
        data = "test data"
        secret = "secret key"
        signature = sign_data(data, secret)

        # Verify correct signature
        self.assertTrue(verify_signature(data, signature, secret))

        # Verify incorrect signature
        self.assertFalse(verify_signature(data, "wrong signature", secret))

        # Verify tampered data
        self.assertFalse(verify_signature("tampered data", signature, secret))

    def test_validate_json_input(self):
        """Test validating JSON input data."""
        # Test with valid data
        data = {
            "name": "John",
            "email": "john@example.com",
            "age": 30
        }
        required_fields = ["name", "email"]
        valid, message = validate_json_input(data, required_fields)
        self.assertTrue(valid)
        self.assertIsNone(message)

        # Test with missing required field
        data = {
            "name": "John"
        }
        valid, message = validate_json_input(data, required_fields)
        self.assertFalse(valid)
        self.assertIn("Missing required field", message)

        # Test with field validators
        def validate_email(email):
            if not email.endswith("@example.com"):
                return False, "Email must be from example.com domain"
            return True, None

        field_validators = {
            "email": validate_email
        }

        data = {
            "name": "John",
            "email": "john@gmail.com"
        }
        valid, message = validate_json_input(data, required_fields, field_validators)
        self.assertFalse(valid)
        self.assertIn("Email must be from example.com domain", message)


if __name__ == '__main__':
    unittest.main()