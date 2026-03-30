import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from calculator import add, subtract, multiply, divide


class TestAdd(unittest.TestCase):
    def test_add_two_positive_numbers(self):
        result = add(2, 3)
        self.assertEqual(result, 5)

    def test_add_negative_numbers(self):
        result = add(-1, -2)
        self.assertEqual(result, -3)

    def test_add_zero(self):
        result = add(5, 0)
        self.assertEqual(result, 5)

    def test_add_floats(self):
        result = add(1.5, 2.5)
        self.assertAlmostEqual(result, 4.0)


class TestSubtract(unittest.TestCase):
    def test_subtract_positive_numbers(self):
        result = subtract(5, 3)
        self.assertEqual(result, 2)

    def test_subtract_resulting_in_negative(self):
        result = subtract(3, 5)
        self.assertEqual(result, -2)

    def test_subtract_zero(self):
        result = subtract(5, 0)
        self.assertEqual(result, 5)


class TestMultiply(unittest.TestCase):
    def test_multiply_positive_numbers(self):
        result = multiply(3, 4)
        self.assertEqual(result, 12)

    def test_multiply_by_zero(self):
        result = multiply(5, 0)
        self.assertEqual(result, 0)

    def test_multiply_negative_numbers(self):
        result = multiply(-2, -3)
        self.assertEqual(result, 6)

    def test_multiply_mixed_sign(self):
        result = multiply(-2, 3)
        self.assertEqual(result, -6)


class TestDivide(unittest.TestCase):
    def test_divide_evenly(self):
        result = divide(10, 2)
        self.assertEqual(result, 5.0)

    def test_divide_with_remainder(self):
        result = divide(7, 2)
        self.assertAlmostEqual(result, 3.5)

    def test_divide_by_zero_raises_error(self):
        with self.assertRaises(ValueError) as ctx:
            divide(10, 0)
        self.assertEqual(str(ctx.exception), "Cannot divide by zero")

    def test_divide_negative_by_positive(self):
        result = divide(-10, 2)
        self.assertEqual(result, -5.0)


if __name__ == "__main__":
    unittest.main()
