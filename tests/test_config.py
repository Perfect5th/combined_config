import argparse
import configparser
import tempfile
import unittest
from unittest import mock

from combined_config import CombinedConfig, ConfigVar


class CombinedConfigTestCase(unittest.TestCase):
    """Tests for the `CombinedConfig` all-in-one config."""

    def test_append(self):
        """`append` adds a config to the end of the collection of configs."""
        config = CombinedConfig()
        dummy_config = mock.Mock()

        config.prepend(object())
        config.append(object())
        config.prepend(object())
        config.append(dummy_config)

        self.assertIs(config._configs[-1], dummy_config)

    def test_defaults(self):
        """An initialized `CombinedConfig` only provides default values."""
        config = CombinedConfig(
            ConfigVar(name="no_default"),
            ConfigVar(name="has_default", default="magical"),
        )

        self.assertEqual(config.values.has_default, "magical")
        self.assertIsNone(config.values.no_default)

    def test_defaulted_values(self):
        """`defaulted_values` is the set of values that have not effectively
        been changed from their defaults.
        """
        config = CombinedConfig(
            ConfigVar(name="some_default", default="farcical"),
            ConfigVar(name="has_default", default="magical"),
            ConfigVar(name="another_default", default="tragical"),
        )

        config.append(
            {
                "some_default": "comedic",
                "another_default": "tragical",
            },
        )

        defaulted = config.defaulted_values
        self.assertIn("has_default", defaulted)
        self.assertIn("another_default", defaulted)

    def test_fallthrough_default(self):
        """If no configs have the value, then the default is provided."""
        config = CombinedConfig(
            ConfigVar("has_default", default="stupendous"),
            ConfigVar("my_variable"),
            ConfigVar("other_variable"),
        )

        config.append({"my_variable": "my_value"})
        config.append({"other_variable": "other_value"})

        self.assertEqual(config.values.my_variable, "my_value")
        self.assertEqual(config.values.other_variable, "other_value")
        self.assertEqual(config.values.has_default, "stupendous")

    def test_find(self):
        """`find` finds the value in the earliest config that contains it."""
        config = CombinedConfig(ConfigVar(name="my_variable"))

        config.append({"my_variable": "my_value"})

        self.assertEqual(config.find("my_variable"), "my_value")

    def test_find_argparse(self):
        """`find` can find values provided by `argparse.ArgumentParser`."""
        config = CombinedConfig(
            ConfigVar(name="my_var1"),
            ConfigVar(name="my_var2"),
        )

        config.append({"my_var1": "haldo", "my_var2": "waldo"})

        parser = argparse.ArgumentParser()
        parser.add_argument("--my-var2")
        parsed = parser.parse_args(["--my-var2", "galdo"])

        config.prepend(parsed)

        self.assertEqual(config.values.my_var1, "haldo")
        self.assertEqual(config.values.my_var2, "galdo")

    def test_find_configparser(self):
        """`find` can find values provided by `configparser.SectionProxy`."""
        config = CombinedConfig(
            ConfigVar(name="my_var1"),
            ConfigVar(name="my_var2"),
        )

        config.append({"my_var1": "haldo"})

        config_file = tempfile.TemporaryFile(mode="w+")
        config_file.write("[config]\nmy_var2 = galdo\n\n")
        config_file.seek(0)
        config_parser = configparser.ConfigParser()
        config_parser.read_file(config_file)

        config.append(config_parser["config"])

        self.assertEqual(config.values.my_var1, "haldo")
        self.assertEqual(config.values.my_var2, "galdo")

        config_file.close()

    def test_prepend(self):
        """`prepend` adds a config to the start of the collection of
        configs.
        """
        config = CombinedConfig()
        dummy_config = mock.Mock()

        config.append(object())
        config.append(object())
        config.append(object())
        config.prepend(dummy_config)

        self.assertIs(config._configs[0], dummy_config)

    def test_provided_args(self):
        """`provided_args` is a collection of values that have been provided by
        CLI argument parsing.
        """
        config = CombinedConfig(
            ConfigVar(name="my_var1", action="store_true", default=False),
            ConfigVar(name="my_var2", default="welp"),
            ConfigVar(name="my_var3", type=float),
        )

        parser = config.make_parser()
        parsed = parser.parse_args(["--my-var1", "--my-var3", "3.7"])

        config.append(parsed)

        self.assertIn("my_var1", config.provided_args)
        self.assertNotIn("my_var2", config.provided_args)
        self.assertIn("my_var3", config.provided_args)

    def test_variables_with_values(self):
        """`variables_with_values` is a collection of variables with non-None
        values.
        """
        config = CombinedConfig(
            ConfigVar(name="my_var1", action="store_true", default=False),
            ConfigVar(name="my_var2", default="welp"),
            ConfigVar(name="my_var3", type=float),
        )

        self.assertEqual(
            config.variables_with_values,
            {
                "my_var1": False,
                "my_var2": "welp",
            },
        )

    def test_make_parser(self):
        """`make_parser` creates an `argparse.ArgumentParser` for the provided
        config vars.
        """
        config = CombinedConfig(
            ConfigVar(
                name="my_var1",
                shortname="v",
                action="store_true",
                default=False,
                metavar="VAR",
            ),
            ConfigVar(name="my_var2", default="welp"),
            ConfigVar(name="my_var3", type=float),
        )

        parser = config.make_parser()
        parsed = parser.parse_args(["-v", "--my-var3", "3.6"])

        config.append(parsed)

        self.assertTrue(config.values.my_var1)
        self.assertEqual(config.values.my_var2, "welp")
        self.assertEqual(config.values.my_var3, 3.6)
