import os
from dotenv import load_dotenv
from src.connections.openai_connection import OpenAIConnection
from src.connections.twitter_connection import TwitterConnection

class ConnectionManager:
    def __init__(self):
        self.connections = {
            'twitter': TwitterConnection(),
            'openai': OpenAIConnection(),
        }

        # Define action parameter requirements
        self.action_params = {
            "get-latest-tweets": {"required": ["username", "count"], "usage": "<username> <count>"},
            "post-tweet": {"required": ["message"], "usage": "<message>"},
            "like-tweet": {"required": ["tweet_id"], "usage": "<tweet_id>"},
            "reply-to-tweet": {"required": ["tweet_id", "message"], "usage": "<tweet_id> <message>"},
            "generate-text": {"required": ["prompt", "system_prompt"], "usage": "<prompt> <system_prompt>"},
            "set-model": {"required": ["model"], "usage": "<model>"},
            "check-model": {"required": [], "usage": ""},
        }

    def configure_connection(self, connection_string: str):
        try:
            connection = self.connections[connection_string]
            connection.configure()
            if connection.is_configured():
                print(f"\n✅ SUCCESSFULLY CONFIGURED CONNECTION: {connection_string}")
            else:
                print(f"\n❌ ERROR CONFIGURING CONNECTION: {connection_string}")
        except KeyError:
            print("\nUnknown connection. Try 'list-connections' to see all supported connections.")
        except Exception as e:
            print(f"\nAn error occurred: {e}")

    def check_connection(self, connection_string: str, verbose: bool = False)-> bool:
        try:
            connection = self.connections[connection_string]
            if connection.is_configured():
                if verbose:
                    print(f"\n✅ SUCCESSFULLY CHECKED CONNECTION: {connection_string}")
                return True
            if verbose:
                print(f"\n❌ ERROR CHECKING CONNECTION: {connection_string}")
            return False
        except KeyError:
            print("\nUnknown connection. Try 'list-connections' to see all supported connections.")
            return False
        except Exception as e:
            print(f"\nAn error occurred: {e}")
            return False

    def list_connections(self):
        print("\nAVAILABLE CONNECTIONS:")
        for connection_key, connection in self.connections.items():
            if connection.is_configured():
                print(f"- {connection_key} : ✅ Configured")
            else:
                print(f"- {connection_key} : ❌ Not Configured")

    def list_actions(self, connection_string: str):
        try:
            connection = self.connections[connection_string]
            if connection.is_configured():
                print(f"\n✅ {connection_string} is configured. You can use any of its actions.")
            else:
                print(f"\n❌ {connection_string} is not configured. You must configure a connection in order to use its actions.")
            print("\nAVAILABLE ACTIONS:")
            for action, details in connection.actions.items():
                print(f"- {action}: {details}")
        except KeyError:
            print("\nUnknown connection. Try 'list-connections' to see all supported connections.")
        except Exception as e:
            print(f"\nAn error occurred: {e}")

    def find_and_perform_action(self, action_string: str, connection_string: str, **kwargs):
        try:
            connection = self.connections[connection_string]
            action_info = connection.actions.get(action_string)
            if not action_info:
                raise KeyError(f"Unknown action: {action_string}")

            if 'input_list' in kwargs:
                args = kwargs.pop('input_list')[3:]  # Skip command, connection, and action
                param_info = self.action_params.get(action_string, {})
                required = param_info.get("required", [])
                
                if len(args) < len(required):
                    print(f"\nError: {action_string} requires {len(required)} arguments")
                    print(f"Usage: agent_action {connection_string} {action_string} {param_info.get('usage', '')}")
                    return None

                # Handle parameters based on action requirements
                if "count" in required:
                    try:
                        kwargs["count"] = int(args[required.index("count")])
                    except ValueError:
                        print("\nError: Count must be a number")
                        return None

                if "message" in required:
                    message_index = required.index("message")
                    message_parts = args[message_index:] if message_index == len(required) - 1 else [args[message_index]]
                    message = ' '.join(message_parts)
                    if message.startswith('"') and message.endswith('"'):
                        message = message[1:-1]
                    kwargs["message"] = message

                # Handle other parameters
                for i, param in enumerate(required):
                    if param not in ["message", "count"] and i < len(args):
                        kwargs[param] = args[i]

            return connection.perform_action(action_string, **kwargs)
            
        except KeyError as e:
            print(f"\nUnknown connection or action: {str(e)}")
            return None
        except ValueError as e:
            print(f"\nInvalid argument: {str(e)}")
            return None
        except Exception as e:
            print(f"\nAn error occurred: {e}")
            return None