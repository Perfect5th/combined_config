# combined_config
[![PyPI](https://img.shields.io/pypi/v/combined-config)](https://pypi.org/project/combined-config/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/combined-config.svg)](https://pypi.org/project/combined-config/)
[![check](https://github.com/perfect5th/combined_config/actions/workflows/check.yml/badge.svg)](https://github.com/perfect5th/combined_config/actions/workflows/check.yml)

 A Python library for stitching multiple configuration sources together in order or priority.

The intention of this library is to provide a type, `CombinedConfig`, that represents all of the
configuration options for a Python project in a format conversant with Python's
[`configparser`](https://docs.python.org/3/library/configparser.html) and
[`argparse`](https://docs.python.org/3/library/argparse.html) modules. A `CombinedConfig` instance
represents an ordering in which ingested configuration values should be searched, and optional
default values for configuration values that have not been provided. A `CombinedConfig` is
instantiated with one or more `ConfigVar` instances, which present fields corresponding to those
provided to
[`argparse.ArgumentParser.add_argument`](https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.add_argument).

## `CombinedConfig`

```python
import configparser
from combined_config import CombinedConfig, ConfigVar

my_config = CombinedConfig(
    ConfigVar(name="arg_with_default", shortname="a", default="my default"),
    ConfigVar(name="switch", action="store_true", default=False, help="Turns on the frobnicator"),
    ConfigVar(name="no_default", type=int),
)

# You can create a `ArgumentParser` from the `CombinedConfig`.
parser = my_config.make_parser()
parsed = parser.parse_args(["-a", "other value", "--no-default", "10", "--switch"])

# Appending a config gives it lower priority than those already added.
my_config.append(parsed)

print(my_config.values.arg_with_default)  # => other value
print(my_config.values.no_default)  # => 10
print(my_config.values.switch)  # => True

config_parser = ConfigParser()
config_parser.read({"my_section": {"no_default": 35}})
# Example contents of "some-other-conf.ini"
# [my_section]
# no_default = 35

# Prepending a config gives it higher priority than those already added.
my_config.prepend(config_parser["my_section"])

print(my_config.values.no_default)  # => 35

# We can also add dictionaries.
my_config.prepend({"arg_with_default": "another other value"})

print(my_config.values.arg_with_default)  # => another other value
```

## `FileBackedConfigMixin`

Commonly, you'll want to be able to easily read and write the configuration from/to file. This can
be done with a subclass of `CombinedConfig` that also subclasses `FileBackedConfigMixin`.

```python
from combined_config import CombinedConfig, ConfigVar, FileBackedConfigMixin


class MyBackedConfig(CombinedConfig, FileBackedConfigMixin):
    # Should be a mapping of ini section names to the `ConfigVar` names that will be stored there.
    # Special value `"__ALL__"` means all keys.
    ini_section_names = {"my_section": "__ALL__"}
    filename = "/tmp/my-config.ini"


my_config = MyBackedConfig(
    ConfigVar(name="arg_with_default", shortname="a", default="my default"),
    ConfigVar(name="switch", action="store_true", default=False, help="Turns on the frobnicator"),
    ConfigVar(name="no_default", type=int),
)

# Load the config from file.
my_config.read()

my_config.prepend({"switch": True})

# Write the config back to file. Only configuration values that differ from their defaults will be
# written.
my_config.write()
```
