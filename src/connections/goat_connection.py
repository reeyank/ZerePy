import logging
import os
import importlib
from typing import Dict, Any, List, Type, get_type_hints, Optional, Union
from dataclasses import is_dataclass
from pydantic import BaseModel, Field

from src.connections.base_connection import BaseConnection, Action, ActionParameter
from goat import PluginBase, ToolBase, WalletClientBase

logger = logging.getLogger("connections.goat_connection")


class GoatConnectionError(Exception):
    """Base exception for Goat connection errors"""

    pass


class GoatConfigurationError(GoatConnectionError):
    """Raised when there are configuration/credential issues"""

    pass


class GoatConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        logger.info("✨ Initializing Goat adapter")

        self._wallet_client: WalletClientBase | None = None
        self._plugins: Dict[str, PluginBase] = {}
        self._action_registry: Dict[str, ToolBase] = {}

        # This calls validate_config, loads plugins and registers actions
        super().__init__(config)

    def _resolve_type(self, raw_value: str, module) -> Any:
        """Resolve a type from a string, either from plugin module or fully qualified path"""
        try:
            # Try to load from plugin module first
            return getattr(module, raw_value)
        except AttributeError:
            try:
                # Try as fully qualified import
                module_path, class_name = raw_value.rsplit(".", 1)
                type_module = importlib.import_module(module_path)
                return getattr(type_module, class_name)
            except (ValueError, ImportError, AttributeError) as e:
                raise GoatConfigurationError(
                    f"Could not resolve type '{raw_value}'"
                ) from e

    def _validate_value(self, raw_value: Any, field_type: Type, module) -> Any:
        """Validate and convert a value to its expected type"""
        # Handle basic types
        if field_type in (str, int, float, bool):
            return field_type(raw_value)

        # Handle Lists
        if hasattr(field_type, "__origin__") and field_type.__origin__ is list:
            if not isinstance(raw_value, list):
                raise ValueError(f"Expected list, got {type(raw_value).__name__}")

            element_type = field_type.__args__[0]
            return [
                self._validate_value(item, element_type, module) for item in raw_value
            ]

        # Handle dynamic types (classes/types that need to be imported)
        if isinstance(raw_value, str):
            return self._resolve_type(raw_value, module)

        raise ValueError(f"Unsupported type: {field_type}")

    def _load_plugin(self, plugin_config: Dict[str, Any]) -> None:
        """Dynamically load plugins from goat_plugins namespace"""
        plugin_name = plugin_config["name"]
        try:
            # Import from goat_plugins namespace
            module = importlib.import_module(f"goat_plugins.{plugin_name}")

            # Get the plugin initializer function
            plugin_initializer = getattr(module, plugin_name)

            # Get the options type from the function's type hints
            type_hints = get_type_hints(plugin_initializer)
            if "options" not in type_hints:
                raise GoatConfigurationError(
                    f"Plugin '{plugin_name}' initializer must have 'options' parameter"
                )

            options_class = type_hints["options"]
            if not is_dataclass(options_class):
                raise GoatConfigurationError(
                    f"Plugin '{plugin_name}' options must be a dataclass"
                )

            # Get the expected fields and their types from the options class
            option_fields = get_type_hints(options_class)

            # Convert and validate the provided args
            validated_args = {}
            raw_args = plugin_config.get("args", {})

            for field_name, field_type in option_fields.items():
                if field_name not in raw_args:
                    raise GoatConfigurationError(
                        f"Missing required option '{field_name}' for plugin '{plugin_name}'"
                    )

                raw_value = raw_args[field_name]

                try:
                    validated_value = self._validate_value(
                        raw_value, field_type, module
                    )
                    validated_args[field_name] = validated_value

                except (ValueError, TypeError) as e:
                    raise GoatConfigurationError(
                        f"Invalid value for option '{field_name}' in plugin '{plugin_name}': {str(e)}"
                    ) from e

            # Create the options instance
            plugin_options = options_class(**validated_args)

            # Initialize the plugin
            plugin_instance: PluginBase = plugin_initializer(options=plugin_options)
            self._plugins[plugin_name] = plugin_instance
            logger.info(f"✨ Loaded plugin: {plugin_name}")

        except ImportError:
            raise GoatConfigurationError(
                f"Failed to import plugin '{plugin_name}' from goat_plugins namespace"
            )
        except AttributeError as e:
            raise GoatConfigurationError(
                f"Plugin '{plugin_name}' does not have expected initializer function"
            )
        except Exception as e:
            raise GoatConfigurationError(
                f"Failed to initialize plugin '{plugin_name}': {str(e)}"
            )

    def _convert_pydantic_to_action_parameters(
        self, model_class: Type[BaseModel]
    ) -> List[ActionParameter]:
        """Convert Pydantic model fields to ActionParameters"""
        parameters = []

        for field_name, field in model_class.model_fields.items():
            # Get field type, handling Optional types
            field_type = field.annotation
            is_optional = False

            # Handle Optional types
            if field_type is not None:
                # Check if it's an Optional type
                origin = getattr(field_type, "__origin__", None)
                if origin is Union:
                    args = getattr(field_type, "__args__", None)
                    if args and type(None) in args:
                        # Get the non-None type from Optional
                        field_type = next(t for t in args if t is not type(None))
                        is_optional = True

            # Get description from Field
            description = field.description or f"Parameter {field_name}"

            # Ensure we have a valid Python type
            if not isinstance(field_type, type):
                # Default to str if we can't determine the type
                field_type = str

            parameters.append(
                ActionParameter(
                    name=field_name,
                    required=not is_optional and field.default is None,
                    type=field_type,
                    description=description,
                )
            )

        return parameters

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate GOAT configuration"""
        required_fields = ["plugins"]
        required_plugin_fields = ["name", "args"]

        missing_fields = [field for field in required_fields if not config.get(field)]
        if missing_fields:
            raise ValueError(
                f"Missing required configuration fields: {', '.join(missing_fields)}"
            )

        for plugin_config in config["plugins"]:
            missing_plugin_fields = [
                field for field in required_plugin_fields if field not in plugin_config
            ]
            if missing_plugin_fields:
                raise ValueError(
                    f"Missing required fields for plugin: {', '.join(missing_plugin_fields)}"
                )

            if not isinstance(plugin_config["args"], dict):
                raise ValueError("args must be a dictionary")

            for arg_name, arg_value in plugin_config["args"].items():
                if not isinstance(arg_name, str):
                    raise ValueError(f"Invalid key for {arg_name}: {arg_value}")
                if not isinstance(arg_value, str):
                    raise ValueError(f"Invalid value for {arg_name}: {arg_value}")

            plugin_name = plugin_config["name"]
            if not plugin_name.isidentifier():
                raise ValueError(
                    f"Invalid plugin name '{plugin_name}'. Must be a valid Python identifier"
                )

            self._load_plugin(plugin_config)

        # required_env_variables = [
        #     "EVM_PRIVATE_KEY",
        #     "EVM_PROVIDER_URL",
        # ]
        # missing_env_variables = [
        #     field for field in required_env_variables if not os.getenv(field)
        # ]
        # if missing_env_variables:
        #     raise ValueError(
        #         f"Missing required environment variables: {', '.join(missing_env_variables)}"
        #     )

        self._is_configured = True

        return config

    def register_actions(self) -> None:
        """Register available actions across loaded plugins"""
        for plugin_instance in self._plugins.values():
            plugins_tools: List[ToolBase] = plugin_instance.get_tools(
                wallet_client=self._wallet_client
            )
            for tool in plugins_tools:
                action_parameters = self._convert_pydantic_to_action_parameters(
                    tool.parameters
                )

                tool_name = f"{plugin_instance.name}-{tool.name}"

                if self.actions.get(tool_name):
                    logger.warning(
                        f"Action {tool_name} is provided by multiple plugins!"
                    )

                self.actions[tool_name] = Action(  # type: ignore
                    name=tool_name,
                    description=tool.description,
                    parameters=action_parameters,
                )
                self._action_registry[tool_name] = tool

    def is_configured(self, verbose: bool = False) -> bool:
        """Check if the connection is properly configured"""
        return self._is_configured

    def perform_action(self, action_name: str, **kwargs) -> Any:
        """Execute a GOAT action using a plugin's tool"""
        action = self.actions.get(action_name)
        if not action:
            raise KeyError(f"Unknown action: {action_name}")

        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        tool = self._action_registry[action_name]
        return tool.execute(kwargs)