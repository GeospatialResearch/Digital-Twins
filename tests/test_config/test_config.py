import os
import unittest

from src import config


class GetEnvVariableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.TEST_VAR_KEY = "TEST_VAR_KEY"

    def test_empty_str_env_var(self):
        # Manually set empty env variable
        os.environ[self.TEST_VAR_KEY] = ""
        with self.assertRaises(KeyError, msg="get_env_variable should raise a KeyError if the env variable is empty"):
            config.get_env_variable(self.TEST_VAR_KEY)

    def test_empty_str_env_var_allow_empty(self):
        # Manually set empty env variable
        os.environ[self.TEST_VAR_KEY] = ""
        self.assertEqual(config.get_env_variable(self.TEST_VAR_KEY, allow_empty=True), "")

    def test_non_existent_env_var(self):
        with self.assertRaises(KeyError,
                               msg="get_env_variable should raise a KeyError if the env variable does not exist"):
            config.get_env_variable("NON_INITIALISED_ENVIRONMENT_VARIABLE_TEST_KEY")

    def test_str_env_var(self):
        test_var_value = "TEST VALUE"
        # Manually set string env variable
        os.environ[self.TEST_VAR_KEY] = test_var_value
        self.assertEqual(config.get_env_variable(self.TEST_VAR_KEY), test_var_value)

    def test_int_env_var(self):
        test_var_value = "10"
        # Manually set string env variable
        os.environ[self.TEST_VAR_KEY] = test_var_value
        self.assertEqual(config.get_env_variable(self.TEST_VAR_KEY, cast_to=int), 10)

    def test_true_bool_env_var(self):
        test_var_value = "True"
        # Manually set string env variable
        os.environ[self.TEST_VAR_KEY] = test_var_value
        self.assertEqual(config.get_env_variable(self.TEST_VAR_KEY, cast_to=bool), True)

    def test_false_bool_env_var(self):
        test_var_value = "F"
        # Manually set string env variable
        os.environ[self.TEST_VAR_KEY] = test_var_value
        self.assertFalse(config.get_env_variable(self.TEST_VAR_KEY, cast_to=bool))

    def test_unknown_bool_env_var(self):
        test_var_value = "UNKNOWN"
        # Manually set string env variable
        os.environ[self.TEST_VAR_KEY] = test_var_value
        with self.assertRaises(ValueError,
                               msg="get_env_variable should raise a key error if variable is being casted to bool but it is not explicitly True or False"):
            config.get_env_variable(self.TEST_VAR_KEY, cast_to=bool)

    def test_default_env_var(self):
        default_string = "default test string"
        self.assertEqual(config.get_env_variable(self.TEST_VAR_KEY, default=default_string), default_string)


if __name__ == '__main__':
    unittest.main()
