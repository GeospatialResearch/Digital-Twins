import unittest

from sqlalchemy.exc import OperationalError

from src.digitaltwin.setup_environment import get_connection_from_profile


class SetupEnvironmentTest(unittest.TestCase):

    def test_connection(self):
        engine = get_connection_from_profile()
        engine.connect()

    def test_incorrect_password(self):
        incorrect_password_config_path = 'tests/setup_environment_test/mock_db_configuration.yml'
        with self.assertRaises(OperationalError):
            get_connection_from_profile(incorrect_password_config_path)


if __name__ == '__main__':
    unittest.main()
