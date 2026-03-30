import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from string_utils import reverse_string, is_palindrome, word_count, capitalize_words


class TestReverseString(unittest.TestCase):
    def test_reverse_simple_string(self):
        result = reverse_string("hello")
        self.assertEqual(result, "olleh")

    def test_reverse_empty_string(self):
        result = reverse_string("")
        self.assertEqual(result, "")

    def test_reverse_single_character(self):
        result = reverse_string("a")
        self.assertEqual(result, "a")

    def test_reverse_palindrome_stays_same(self):
        result = reverse_string("racecar")
        self.assertEqual(result, "racecar")


class TestIsPalindrome(unittest.TestCase):
    def test_simple_palindrome(self):
        result = is_palindrome("racecar")
        self.assertTrue(result)

    def test_non_palindrome(self):
        result = is_palindrome("hello")
        self.assertFalse(result)

    def test_palindrome_with_mixed_case(self):
        result = is_palindrome("Racecar")
        self.assertTrue(result)

    def test_palindrome_with_spaces(self):
        result = is_palindrome("taco cat")
        self.assertTrue(result)

    def test_empty_string_is_palindrome(self):
        result = is_palindrome("")
        self.assertTrue(result)


class TestWordCount(unittest.TestCase):
    def test_count_multiple_words(self):
        result = word_count("hello world foo")
        self.assertEqual(result, 3)

    def test_count_single_word(self):
        result = word_count("hello")
        self.assertEqual(result, 1)

    def test_count_empty_string(self):
        result = word_count("")
        self.assertEqual(result, 0)

    def test_count_whitespace_only(self):
        result = word_count("   ")
        self.assertEqual(result, 0)


class TestCapitalizeWords(unittest.TestCase):
    def test_capitalize_lowercase_words(self):
        result = capitalize_words("hello world")
        self.assertEqual(result, "Hello World")

    def test_capitalize_already_capitalized(self):
        result = capitalize_words("Hello World")
        self.assertEqual(result, "Hello World")

    def test_capitalize_single_word(self):
        result = capitalize_words("hello")
        self.assertEqual(result, "Hello")

    def test_capitalize_all_uppercase(self):
        result = capitalize_words("HELLO WORLD")
        self.assertEqual(result, "Hello World")


if __name__ == "__main__":
    unittest.main()
