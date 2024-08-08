import os
import unittest

import pytest
from sqlalchemy.exc import OperationalError

from src import config
from src.digitaltwin import setup_environment


class SetupEnvironmentTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up arguments used for testing."""
        # flag for checking if tests requiring database to be active should run
        cls.run_database_integration_tests = config.EnvVariable.TEST_DATABASE_INTEGRATION
        cls.DATABASE_SKIP_REASON = """TEST_DATABASE_INTEGRATION env var is not True, so the test is skipped.
            This is intentional at all times on the GitHub Actions."""

    def test_connection(self):
        """Check a connection to the database can be made with the default parameters of get_connection_from_profile"""
        # Skip this if database tests are not intended to be run in this environment
        if not self.run_database_integration_tests:
            pytest.skip(self.DATABASE_SKIP_REASON)
        engine = setup_environment.get_connection_from_profile()
        connection = engine.connect()
        self.assertFalse(connection.closed,
                         msg="The connection to the database failed and is needed for these tests.")

    def test_incorrect_password(self):
        """Ensure that when a bad password is given to the database, the connection fails and an exception is raised"""
        # Skip this if database tests are not intended to be run in this environment
        if not self.run_database_integration_tests:
            pytest.skip(self.DATABASE_SKIP_REASON)
        self.test_connection()  # This test case requires an active connection to trust the result.
        # Override the variables supplied by the .env file with an incorrect password
        os.environ["POSTGRES_PASSWORD"] = "incorrect_password"
        with self.assertRaises(OperationalError,
                               msg="get_connection_from_profile should raise an OperationalError"
                                   " if the password supplied is incorrect"):
            setup_environment.get_connection_from_profile()


if __name__ == '__main__':
    unittest.main()
