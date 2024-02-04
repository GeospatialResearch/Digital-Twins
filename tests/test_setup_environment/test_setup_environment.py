import os
import sys
import unittest

import pytest
from sqlalchemy.exc import OperationalError

from src.digitaltwin import setup_environment


class SetupEnvironmentTest(unittest.TestCase):

    @pytest.mark.skipif(
        sys.platform != "win32",
        reason="This test only runs on local dev machines. It is not set up to integrate into a test database")
    def test_connection(self):
        """Check a connection to the database can be made with the default parameters of get_connection_from_profile"""
        engine = setup_environment.get_connection_from_profile()
        connection = engine.connect()
        self.assertFalse(connection.closed,
                         "The connection to the database failed")  # Check that the connection is open

    @pytest.mark.skipif(
        sys.platform != "win32",
        reason="This test only runs on local dev machines. It is not set up to integrate into a test database")
    def test_incorrect_password(self):
        """Ensure that when a bad password is given to the database, the connection fails and an exception is raised"""
        os.environ["POSTGRES_PASSWORD"] = "EXAMPLE AAA123 INCORRECT PASSWORD"
        with self.assertRaises(OperationalError,
                               msg="get_connection_from_profile should raise an OperationalError if the password supplied is incorrect"):
            setup_environment.get_connection_from_profile()


if __name__ == '__main__':
    unittest.main()
