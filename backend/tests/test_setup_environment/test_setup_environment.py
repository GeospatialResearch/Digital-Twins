import unittest

from sqlalchemy.exc import OperationalError

from ...src.util import setup_environment


class SetupEnvironmentTest(unittest.TestCase):

    @unittest.skip("Skipping until we work on https://github.com/GeospatialResearch/Digital-Twins/issues/23")
    def test_connection(self):
        """Check a connection to the database can be made with the default parameters of get_connection_from_profile"""
        engine = setup_environment.get_connection_from_profile()
        connection = engine.connect()
        self.assertFalse(connection.closed,
                         "The connection to the database failed")  # Check that the connection is open

    @unittest.skip("Skipping until we work on https://github.com/GeospatialResearch/Digital-Twins/issues/23")
    def test_incorrect_password(self):
        """Ensure that when a bad password is given to the database, the connection fails and an exception is raised"""
        incorrect_password_config_path = 'tests/test_setup_environment/mock_db_configuration.yml'
        with self.assertRaises(OperationalError,
                               msg="get_connection_from_profile should raise an OperationalError if the password supplied is incorrect"):
            setup_environment.get_connection_from_profile(
                incorrect_password_config_path)


if __name__ == '__main__':
    unittest.main()
