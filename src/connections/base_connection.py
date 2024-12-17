from abc import ABC, abstractmethod

class BaseConnection(ABC):

    def __init__(self):
        self.actions = {}

    @property
    @abstractmethod
    def is_llm_provider(self):
        pass  # Abstract property, must be implemented by subclasses

    @abstractmethod
    def configure(self, **kwargs):
        """
        Configure the connection. This should store necessary credentials
        and mark the connection as configured.
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """
        Check if the connection is ready for use.
        """
        pass

    @abstractmethod
    def perform_action(self, action_name: str, **kwargs):
        """
        Perform an action supported by this connection.
        Args:
            action_name (str): The action to perform.
            **kwargs: Data required for the action.
        Returns:
            Any: The result of the action.
        """
        for action in self.actions.keys():
            if action_name == action:
                # Run action function
                result = self.actions[action](self, **kwargs)
                return result

        raise Exception(f"Unknown action: {action_name}")
