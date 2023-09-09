import argparse
import configparser
import os
import tempfile
import unittest
from operator import itemgetter

from combined_config import (
    CombinedConfig,
    ConfigException,
    ConfigVar,
    FileBackedConfigMixin,
)


class ConfigVarTestCase(unittest.TestCase):
    """Tests for the `ConfigVar` dataclass."""

    def test_is_bool(self):
        """`is_bool` returns True if `type` is explicitly `bool` or if it can be derived as such."""
        var = ConfigVar("my-bool", type=bool)
        self.assertTrue(var.is_bool)

        var = ConfigVar("my-bool", action="store_true")
        self.assertTrue(var.is_bool)

        var = ConfigVar("my-bool", action="store_false")
        self.assertTrue(var.is_bool)

        var = ConfigVar("my-bool", default=True)
        self.assertTrue(var.is_bool)

        var = ConfigVar("not-bool", default="stringly")
        self.assertFalse(var.is_bool)


class CombinedConfigTestCase(unittest.TestCase):
    """Tests for the `CombinedConfig` all-in-one config."""

    def test_attribute_error(self):
        """Accessing a non-existing attribute raises `AttributeError`."""
        config = CombinedConfig(ConfigVar("something", default="intheway"))

        self.assertRaises(AttributeError, getattr, config.values, "nothing")

    def test_append(self):
        """`append` adds a config to the end of the collection of configs."""
        config = CombinedConfig()
        dummy_config = {"real": "one"}

        config.prepend({})
        config.append({})
        config.prepend({})
        config.append(dummy_config)

        self.assertIs(config._configs[-1], dummy_config)

    def test_unrecognized_type(self):
        """raises a `ConfigException` if the type is unrecognized on `append` and `prepend`. If one
        somehow gets into the deque, raises `ConfigException` upon hitting it when getting values
        """

        class UnrecognizedType:
            pass

        config = CombinedConfig(ConfigVar("anything"))

        with self.assertRaises(ConfigException) as cm:
            config.append(UnrecognizedType())

        self.assertIn("UnrecognizedType", str(cm.exception))

        with self.assertRaises(ConfigException) as cm:
            config.prepend(UnrecognizedType())

        self.assertIn("UnrecognizedType", str(cm.exception))

        config._configs.append(UnrecognizedType())

        with self.assertRaises(ConfigException) as cm:
            config.values.anything

        self.assertIn("UnrecognizedType", str(cm.exception))

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

    def test_iterator(self):
        """`CombinedConfig.values` objects can be iterators."""
        config = CombinedConfig(
            ConfigVar("once", default="shame on you"),
            ConfigVar("twice", default="shame on me"),
        )

        iterator = iter(config.values)

        first = next(iterator)
        second = next(iterator)
        self.assertRaises(StopIteration, next, iterator)

        self.assertEqual(first, "once")
        self.assertEqual(second, "twice")

        as_tuples = [(k, v) for k, v in config.values.items()]
        self.assertEqual(
            as_tuples, [("once", "shame on you"), ("twice", "shame on me")]
        )

    def test_key_error(self):
        """Subscript-accessing a nonexistent var raises a `KeyError`."""
        config = CombinedConfig(ConfigVar("something", default="borrowed"))

        self.assertRaises(KeyError, itemgetter("nothing"), config.values)

    def test_len(self):
        """`CombinedConfig.values` has a reasonable length."""
        config = CombinedConfig(
            ConfigVar("wynken"), ConfigVar("blynken"), ConfigVar("nod")
        )

        self.assertEqual(len(config.values), 3)

    def test_prepend(self):
        """`prepend` adds a config to the start of the collection of
        configs.
        """
        config = CombinedConfig()
        dummy_config = {"real": "one"}

        config.append({})
        config.append({})
        config.append({})
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


class FileBackedConfigMixinTestCase(unittest.TestCase):
    """Tests for the `FileBackedConfigMixin`, providing ini-formatted saving of configs."""

    def test_subclass_not_combined_config(self):
        """If a subclass is not a `CombinedConfig`, raises `AssertionError`."""
        with self.assertRaises(AssertionError) as cm:

            class MyNonConfig(FileBackedConfigMixin):
                pass

        self.assertIn("CombinedConfig", str(cm.exception))

    def test_subclass_no_filename(self):
        """If a subclass does not have a `filename` attribute, raises `AssertionError`."""
        with self.assertRaises(AssertionError) as cm:

            class MyNoFilename(CombinedConfig, FileBackedConfigMixin):
                pass

        self.assertIn("filename", str(cm.exception))

    def test_read(self):
        """`read` appends an ini-formatted file to the config."""
        config_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
        self.addCleanup(os.remove, config_file.name)

        class MyConfig(CombinedConfig, FileBackedConfigMixin):
            ini_section_names = {"testsection": "__ALL__"}
            filename = config_file.name

        config_file.write("[testsection]\n" "four = score\n" "and = seven\n\n")
        config_file.close()

        config = MyConfig(
            ConfigVar("four"),
            ConfigVar("and"),
            ConfigVar("years", default="ago"),
        )

        config.append({"four": "thousand"})
        config.read()

        self.assertEqual(config.values.four, "thousand")
        self.assertEqual(config.values["and"], "seven")
        self.assertEqual(config.values.years, "ago")

    def test_write(self):
        """`write` writes config vars to their respective ini sections."""
        config_file = tempfile.NamedTemporaryFile(delete=False)
        config_file.close()
        self.addCleanup(os.remove, config_file.name)

        class MyConfig(CombinedConfig, FileBackedConfigMixin):
            ini_section_names = {
                "abraham": ("four", "and"),
                "lincoln": (
                    "years",
                    "our",
                ),
            }
            filename = config_file.name

        config = MyConfig(
            ConfigVar("four"),
            ConfigVar("and"),
            ConfigVar("years"),
            ConfigVar("our"),
        )

        config.append(
            {"four": "score", "and": "seven", "years": "ago", "our": "fathers"}
        )
        config.write()

        with open(config_file.name) as config_fp:
            config_parser = configparser.ConfigParser()
            config_parser.read_file(config_fp)

        self.assertEqual(config.values.four, config_parser["abraham"]["four"])
        self.assertEqual(config.values["and"], config_parser["abraham"]["and"])
        self.assertEqual(config.values.years, config_parser["lincoln"]["years"])
        self.assertEqual(config.values.our, config_parser["lincoln"]["our"])

    def test_write_ALL(self):
        """`write` writes all config vars to the section if it has special value `"__ALL__"`."""
        config_file = tempfile.NamedTemporaryFile(delete=False)
        config_file.close()
        self.addCleanup(os.remove, config_file.name)

        class MyConfig(CombinedConfig, FileBackedConfigMixin):
            ini_section_names = {"log cabin": "__ALL__"}
            filename = config_file.name

        config = MyConfig(
            ConfigVar("four"),
            ConfigVar("and"),
            ConfigVar("years"),
            ConfigVar("our"),
        )

        config.append(
            {"four": "score", "and": "seven", "years": "ago", "our": "fathers"}
        )
        config.write()

        with open(config_file.name) as config_fp:
            config_parser = configparser.ConfigParser()
            config_parser.read_file(config_fp)

        section = config_parser["log cabin"]
        self.assertEqual(config.values.four, section["four"])
        self.assertEqual(config.values["and"], section["and"])
        self.assertEqual(config.values.years, section["years"])
        self.assertEqual(config.values.our, section["our"])

    def test_write_defaults(self):
        """`write` does not write any config vars that match their defaults."""
        config_file = tempfile.NamedTemporaryFile(delete=False)
        config_file.close()
        self.addCleanup(os.remove, config_file.name)

        class MyConfig(CombinedConfig, FileBackedConfigMixin):
            ini_section_names = {"gettysburg": "__ALL__"}
            filename = config_file.name

        config = MyConfig(
            ConfigVar("four", default="score"),
            ConfigVar("and", default="eight"),
            ConfigVar("years"),
            ConfigVar("our"),
            ConfigVar("brought", default="forth"),
        )

        config.append(
            {"four": "score", "and": "seven", "years": "ago", "our": "fathers"}
        )
        config.write()

        with open(config_file.name) as config_fp:
            config_parser = configparser.ConfigParser()
            config_parser.read_file(config_fp)

        section = config_parser["gettysburg"]
        self.assertNotIn("four", section)
        self.assertEqual(config.values["and"], section["and"])
        self.assertEqual(config.values.years, section["years"])
        self.assertEqual(config.values.our, section["our"])
        self.assertNotIn("brought", section)
