import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from user_validator import validate_email, validate_username, validate_age


class TestValidateEmail(unittest.TestCase):
    def test_valid_email(self):
        result = validate_email("user@example.com")
        self.assertTrue(result)

    def test_email_missing_at_sign(self):
        result = validate_email("userexample.com")
        self.assertFalse(result)

    def test_email_missing_domain(self):
        result = validate_email("user@")
        self.assertFalse(result)

    def test_email_with_subdomain(self):
        result = validate_email("user@mail.example.com")
        self.assertTrue(result)

    def test_email_with_plus_sign(self):
        result = validate_email("user+tag@example.com")
        self.assertTrue(result)

    def test_empty_email(self):
        result = validate_email("")
        self.assertFalse(result)


class TestValidateUsername(unittest.TestCase):
    def test_valid_username(self):
        result = validate_username("john_doe")
        self.assertTrue(result)

    def test_username_too_short(self):
        result = validate_username("ab")
        self.assertFalse(result)

    def test_username_too_long(self):
        result = validate_username("a" * 21)
        self.assertFalse(result)

    def test_username_at_minimum_length(self):
        result = validate_username("abc")
        self.assertTrue(result)

    def test_username_at_maximum_length(self):
        result = validate_username("a" * 20)
        self.assertTrue(result)

    def test_username_with_special_characters(self):
        result = validate_username("user@name")
        self.assertFalse(result)

    def test_username_with_spaces(self):
        result = validate_username("user name")
        self.assertFalse(result)


class TestValidateAge(unittest.TestCase):
    def test_valid_age(self):
        result = validate_age(25)
        self.assertTrue(result)

    def test_age_zero(self):
        result = validate_age(0)
        self.assertTrue(result)

    def test_age_at_upper_bound(self):
        result = validate_age(150)
        self.assertTrue(result)

    def test_negative_age_raises_error(self):
        with self.assertRaises(ValueError):
            validate_age(-1)

    def test_age_above_limit_raises_error(self):
        with self.assertRaises(ValueError):
            validate_age(151)

    def test_non_integer_age_raises_type_error(self):
        with self.assertRaises(TypeError):
            validate_age("twenty")

    def test_float_age_raises_type_error(self):
        with self.assertRaises(TypeError):
            validate_age(25.5)


if __name__ == "__main__":
    unittest.main()
