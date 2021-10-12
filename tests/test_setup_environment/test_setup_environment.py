import unittest

from sqlalchemy.exc import OperationalError

from src.digitaltwin import setup_environment


class SetupEnvironmentTest(unittest.TestCase):

    def test_connection(self):
        """Check a connection to the database can be made with the default parameters of get_connection_from_profile"""
        engine = setup_environment.get_connection_from_profile()
        connection = engine.connect()
        self.assertFalse(connection.closed,
                         "The connection to the database failed")  # Check that the connection is open



if __name__ == '__main__':
    unittest.main()
