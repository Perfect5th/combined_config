import argparse
import configparser
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from functools import singledispatchmethod
from typing import Any, Dict, Iterator, List, Optional, Protocol, Set, Union


CONFIG_TYPES = {
    argparse.Namespace,
    configparser.SectionProxy,
    dict,
}


class ConfigException(Exception):
    """A generic exception raised when configuration errors occur."""


@dataclass
class ConfigVar:
    """A representation of a single config variable, with everything needed to
    populate a `CombinedConfig` from various config sources.

    Most attributes have the same meaning as those provided to
    `ArgumentParser.add_argument`.
    """

    name: str
    shortname: Optional[str] = None
    action: Optional[str] = None
    default: Optional[Any] = None
    type: Optional[type] = None
    help: Optional[str] = None
    metavar: Optional[str] = None

    @property
    def is_bool(self) -> bool:
        """Whether this object's configuration variable type can be interpreted
        as a bool.
        """
        return (
            self.type == bool
            or self.action in ("store_true", "store_false")
            or isinstance(self.default, bool)
        )

    @property
    def parser_args(self) -> List[str]:
        """The object's values in a format suitable to pass as the positional
        arguments to `argparse.ArgumentParser.add_argument`.
        """
        args = ["--" + self.name.replace("_", "-")]

        if self.shortname:
            args.append("-" + self.shortname)

        return args

    @property
    def parser_kwargs(self) -> Dict[str, Any]:
        """The object's values in a format suitable to pass as the keyword
        arguments to `argparse.ArgumentParser.add_argument`.
        """
        kwargs: Dict[str, Any] = {
            "action": self.action,
            "help": self.help,
        }

        if self.action not in ("store_true", "store_false"):
            kwargs["type"] = self.type
            kwargs["metavar"] = self.metavar

        return kwargs


class CombinedConfig:
    """One config to rule them all. A config-combiner that does the combining
    in a configurable way. Config values should be accessed via the `values`
    attribute.

    The resulting config is flat to maintain comparability between varying
    config sources. If you need a hierarchical config, this is not the config
    for you.

    Configuration variables are provided as a collection of `ConfigVar`s, in
    which defaults (and other settings) can be specified.

    :param ConfigVar config_vars: The variables that will make up
        this configuration.
    """

    class Values(Mapping):
        """A view into the available configuration variables. Configs are
        searched in the order they were added. If a value is not found in any,
        the default is provided."""

        def __init__(self, config):
            self._config = config

        def __getattr__(self, name: str) -> Any:
            if name not in self._config.config_vars:
                raise AttributeError()

            return self._config.find(name)

        def __getitem__(self, key: str) -> Any:
            if key not in self._config.config_vars:
                raise KeyError()

            return self._config.find(key)

        def __iter__(self):
            return iter(self._config.config_vars)

        def __len__(self):
            return len(self._config.config_vars)

    def __init__(self, *config_vars: ConfigVar):
        self._configs: deque = deque()

        self.config_vars = {}
        self.values = self.Values(self)
        self.defaults = {}

        for config_var in config_vars:
            self.config_vars[config_var.name] = config_var

            if config_var.default is not None:
                self.defaults[config_var.name] = config_var.default

    def append(self, config: Any) -> None:
        """Adds `config` to the end of the collection of configs."""
        if type(config) not in CONFIG_TYPES:
            raise ConfigException(
                f"Don't know how to fetch values from config with type {type(config)}",
            )

        self._configs.append(config)

    @property
    def defaulted_values(self) -> Set[str]:
        """The set of variables that still have the same value as their
        defaults.
        """
        return {
            k
            for k in self.config_vars.keys()
            if k in self.defaults and self.find(k) == self.defaults[k]
        }

    def find(self, key: str) -> Any:
        """Search the configs in-order for `key`.

        :param str key: The name of the value to look for.
        :returns Any: The value found. None if not found.
        """
        for config in self._configs:
            value = self._get_value(config, key)

            if value is not None:
                return value

        return self.defaults.get(key)

    def make_parser(self) -> argparse.ArgumentParser:
        """Produces an `ArgumentParser` suitable for parsing our config_vars.
        We suppress defaults because we handle those in our own logic."""
        parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)

        for config_var in self.config_vars.values():
            parser.add_argument(
                *config_var.parser_args,
                **config_var.parser_kwargs,
            )

        return parser

    def prepend(self, config: Any) -> None:
        """Adds `config` to the start of the collection of configs."""
        if type(config) not in CONFIG_TYPES:
            raise ConfigException(
                f"Don't know how to fetch values from config with type {type(config)}",
            )

        self._configs.appendleft(config)

    @property
    def provided_args(self) -> Set[str]:
        """The set of values that have been provided by `ArgumentParser`s."""
        return {
            k
            for k in self.config_vars.keys()
            if any((isinstance(s, argparse.Namespace) for s in self._get_sources(k)))
        }

    @property
    def variables_with_values(self) -> Dict[str, Any]:
        """The variables that have non-None values."""
        values = {}

        for k in self.config_vars.keys():
            value = self.values[k]

            if value is not None:
                values[k] = value

        return values

    def _get_sources(self, key: str) -> Iterator[Any]:
        """Gets all configs that are currently providing the value for
        `key`.
        """
        for config in self._configs:
            value = self._get_value(config, key)

            if value is not None:
                yield config

    @singledispatchmethod
    def _get_value(self, config, key: str) -> Any:
        raise ConfigException(
            f"Don't know how to fetch values from config with type {type(config)}",
        )

    @_get_value.register
    def _(self, config: dict, key: str) -> Any:
        return config.get(key)

    @_get_value.register
    def _(self, config: argparse.Namespace, key: str) -> Any:
        return getattr(config, key, None)

    @_get_value.register
    def _(self, config: configparser.SectionProxy, key: str) -> Any:
        return config.get(key)


class FileBackedConfig(Protocol):
    def append(self, config: Any) -> None:
        ...

    @property
    def defaulted_values(self) -> Set[str]:
        ...

    @property
    def filename(self) -> str:
        ...

    @property
    def ini_section_names(self) -> Dict[str, Union[str, List[str]]]:
        ...

    @property
    def provided_args(self) -> Set[str]:
        ...

    @property
    def variables_with_values(self) -> Dict[str, Any]:
        ...


class FileBackedConfigMixin:
    """A mixin providing methods to back-up a `CombinedConfig`."""

    ini_section_names = {"CONFIG": "__ALL__"}

    def __init_subclass__(cls, *args, **kwargs):
        assert issubclass(
            cls,
            CombinedConfig,
        ), "FileBackedConfigMixin should only be used on CombinedConfigs."
        assert hasattr(cls, "filename"), (
            "To use FileBackedConfigMixin, you need to define a `filename` "
            "class attribute or property."
        )

    def read(self: FileBackedConfig) -> None:
        """Reads configuration from an ini-formatted configuration file,
        underriding the current config variables with it.

        :param filename: a file to read from instead of `self.filename`.
        :type str or None:
        """
        config_parser = configparser.ConfigParser()

        with open(self.filename) as fp:
            config_parser.read_file(fp)

        for section_name in self.ini_section_names.keys():
            if config_parser.has_section(section_name):
                self.append(config_parser[section_name])

    def write(self: FileBackedConfig) -> None:
        """Writes back configuration to the configuration file. Anything that
        is unset or set to its default is not written.

        We make sure to read the current config file first to ensure we don't
        delete anything that pre-exists this write. We use `configparser` for
        this, but since `CombinedConfig` represents a flat config, we determine
        our sections using `ini_section_names`. A value of "__ALL__" for a
        section name means all values should go there.

        :param filename: A file to write to instead of `self.filename`.
        :type str or None:
        """
        config_parser = configparser.ConfigParser()

        defaulted = self.defaulted_values
        provided = self.provided_args
        variables = {
            k: v
            for k, v in self.variables_with_values.items()
            if k in provided or k not in defaulted
        }

        values: Dict[str, dict] = {k: {} for k in self.ini_section_names.keys()}
        for section_name, config_vars in self.ini_section_names.items():
            if config_vars == "__ALL__":
                values = {section_name: variables}
                break

            for config_var in config_vars:
                if config_var in variables:
                    values[section_name][config_var] = variables[config_var]

        with open(self.filename, "r") as fp:
            config_parser.read_file(fp)

        config_parser.read_dict(values)

        with open(self.filename, "w") as fp:
            config_parser.write(fp)
