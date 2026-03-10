# Copyright © 2021-2026 Geospatial Research Institute Toi Hangarau
# LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for utils.py"""
import unittest

from eddie.digitaltwin.utils import retry_function


class RetryFunctionTest(unittest.TestCase):
    """Tests retry_function implementation"""
    MAX_RETRIES = 3  # Number of retries until an exception is propogated.
    DELAY = 0.001  # Low delay between retries to run the test quickly.

    class ExpectedTestError(Exception):
        """Exception that is expected to occur and be caught within retry_function."""
        pass

    class NotExpectedTestError(Exception):
        """An exception that is not expected by retry_function."""
        pass

    def setUp(self):
        """Sets up the test case before each test is run."""
        self.number_of_func_calls = 0

    def func_raise_exception(self) -> None:
        """Raise an expected exception immediately, to test that retry_function works as expected.."""
        self.number_of_func_calls += 1
        raise self.ExpectedTestError

    def test_retry_func_raises_expected_exception(self):
        with self.assertRaises(self.ExpectedTestError):
            retry_function(
                self.func_raise_exception,
                self.MAX_RETRIES,
                self.DELAY,
                self.ExpectedTestError
            )

    def test_retry_func_accepts_multiple_exceptions(self):
        with self.assertRaises(self.ExpectedTestError):
            retry_function(
                self.func_raise_exception,
                self.MAX_RETRIES,
                self.DELAY,
                (self.ExpectedTestError, self.NotExpectedTestError)
            )

    def test_retry_func_accepts_base_exception(self):
        with self.assertRaises(self.ExpectedTestError):
            retry_function(
                self.func_raise_exception,
                self.MAX_RETRIES,
                self.DELAY,
                Exception
            )

    def test_retry_func_returns_expected(self):
        """Tests that a successful func returns the correct value."""
        expected = "abcd test value"
        actual = retry_function(
            lambda: expected,
            self.MAX_RETRIES,
            self.DELAY,
            self.NotExpectedTestError
        )
        self.assertEqual(expected, actual)

    def test_retry_func_called_correct_num_times(self):
        """Test that the retry_function calls func exactly max_retries times if it is failing"""
        max_retries = 7
        with self.assertRaises(self.ExpectedTestError):
            retry_function(
                self.func_raise_exception,
                max_retries,
                self.DELAY,
                self.ExpectedTestError
            )
        self.assertEqual(max_retries + 1, self.number_of_func_calls)

    def test_retry_func_raises_raises_immediately_if_wrong_error(self):
        """Tests that the correct exceptions is raised immediately if an error is not caught."""
        with self.assertRaises(self.ExpectedTestError):
            retry_function(
                self.func_raise_exception,
                self.MAX_RETRIES,
                self.DELAY,
                self.NotExpectedTestError,
            )
        self.assertEqual(1, self.number_of_func_calls)

    def test_retry_func_zero_reties(self):
        """Tests that even with 0 retries the function is called at least once."""
        with self.assertRaises(self.ExpectedTestError):
            retry_function(
                self.func_raise_exception,
                0,
                self.DELAY,
                self.ExpectedTestError
            )
        self.assertEqual(1, self.number_of_func_calls)

    def test_retry_func_zero_delay(self):
        """Tests that even with 0 delay the function still works"""
        with self.assertRaises(self.ExpectedTestError):
            retry_function(
                self.func_raise_exception,
                self.MAX_RETRIES,
                0,
                self.ExpectedTestError
            )
        self.assertEqual(self.MAX_RETRIES + 1, self.number_of_func_calls)


if __name__ == '__main__':
    unittest.main()
