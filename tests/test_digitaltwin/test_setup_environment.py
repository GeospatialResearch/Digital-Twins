import os
import unittest

from sqlalchemy.exc import OperationalError

from src.digitaltwin import setup_environment


class SetupEnvironmentTest(unittest.TestCase):

    @unittest.skip("Skipping until we work on https://github.com/GeospatialResearch/Digital-Twins/issues/23")
    def test_connection(self):
        """Check a connection to the database can be made with the default parameters of get_connection_from_profile"""
        engine = setup_environment.get_connection_from_profile()
        connection = engine.connect()
        self.assertFalse(connection.closed,
                         msg="The connection to the database failed")  # Check that the connection is open

    @unittest.skip("Skipping until we work on https://github.com/GeospatialResearch/Digital-Twins/issues/23")
    def test_incorrect_password(self):
        """Ensure that when a bad password is given to the database, the connection fails and an exception is raised"""
        # Override the variables supplied by the .env file with an incorrect password
        os.environ["POSTGRES_PASSWORD"] = "incorrect_password"
        with self.assertRaises(OperationalError,
                               msg="get_connection_from_profile should raise an OperationalError if the password supplied is incorrect"):
            setup_environment.get_connection_from_profile()


if __name__ == '__main__':
    unittest.main()
