import os
import platform
import unittest

import pytest
from sqlalchemy.exc import OperationalError

from src.digitaltwin import setup_environment


class SetupEnvironmentTest(unittest.TestCase):

    @pytest.mark.skipif(
        platform.system() != "Windows",
        reason="This test only runs on local dev machines with a database running. "
               "It is not set up to integrate into a test suite.")
    def test_connection(self):
        """Check a connection to the database can be made with the default parameters of get_connection_from_profile"""
        engine = setup_environment.get_connection_from_profile()
        connection = engine.connect()
        self.assertFalse(connection.closed,
                         msg="The connection to the database failed and is needed for these tests.")

    @pytest.mark.skipif(
        platform.system() != "Windows",
        reason="This test only runs on local dev machines with a database running. "
               "It is not set up to integrate into a test suite.")
    def test_incorrect_password(self):
        """Ensure that when a bad password is given to the database, the connection fails and an exception is raised"""
        # Override the variables supplied by the .env file with an incorrect password
        self.test_connection()  # This test case requires an active connection to trust the result.
        os.environ["POSTGRES_PASSWORD"] = "incorrect_password"
        with self.assertRaises(OperationalError,
                               msg="get_connection_from_profile should raise an OperationalError"
                                   " if the password supplied is incorrect"):
            setup_environment.get_connection_from_profile()


if __name__ == '__main__':
    unittest.main()
