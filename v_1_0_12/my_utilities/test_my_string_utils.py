import unittest
from my_utilities.my_string_utils import reverse_string

class TestStringUtils(unittest.TestCase):

    def test_reverse_string_empty(self):
        self.assertEqual(reverse_string(""), "")

    def test_reverse_string_single_char(self):
        self.assertEqual(reverse_string("a"), "a")

    def test_reverse_string_palindrome(self):
        self.assertEqual(reverse_string("madam"), "madam")

    def test_reverse_string_normal(self):
        self.assertEqual(reverse_string("hello"), "olleh")

    def test_reverse_string_with_spaces(self):
        self.assertEqual(reverse_string("hello world"), "dlrow olleh")

    def test_reverse_string_with_numbers_and_symbols(self):
        self.assertEqual(reverse_string("123!@#"), "#@!321")

if __name__ == '__main__':
    unittest.main()
