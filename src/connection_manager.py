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

    def configure_connection(self, connection_string: str):
        try:
            # Match connection string to a supported connection
            connection = self.connections[connection_string]
            # Run configuration function
            connection.configure()
            # If configuration was successful, add connection to list
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
            # Match connection string to a supported connection
            connection = self.connections[connection_string]
            # If configuration was successful, add connection to list
            if connection.is_configured():
                if verbose:
                    print(f"\n✅ SUCCESSFULLY CHECKED CONNECTION: {connection_string}")
                return True
            else:
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
            # Match connection string to a supported connection
            connection = self.connections[connection_string]

            # Tell the user whether the connection is configured or not
            if connection.is_configured():
                print(f"\n✅ {connection_string} is configured. You can use any of its actions.")
            else:
                print(f"\n❌ {connection_string} is not configured. You must configure a connection in order to use its actions.")

            # List available actions
            print("\nAVAILABLE ACTIONS:")
            for action, details in connection.actions.items():
                print(f"- {action}: {details}")
        except KeyError:
            print("\nUnknown connection. Try 'list-connections' to see all supported connections.")
        except Exception as e:
            print(f"\nAn error occurred: {e}")

    def find_and_perform_action(self, action_string: str, connection_string: str, **kwargs):
        try:
            # Get the connection
            connection = self.connections[connection_string]
        
            # Get the action info
            action_info = connection.actions.get(action_string)
            if not action_info:
                raise KeyError(f"Unknown action: {action_string}")
        
            # Extract arguments based on input list
            if 'input_list' in kwargs:
                input_list = kwargs.pop('input_list')
                # Skip first three elements (command, connection, and action name)
                args = input_list[3:]
            
                if len(args) > 0:
                    # Handle different actions
                    if action_string == "get-latest-tweets":
                        if len(args) >= 2:
                            kwargs['username'] = args[0]
                            try:
                                kwargs['count'] = int(args[1])
                            except ValueError:
                                print("\nError: Count must be a number")
                                return None
                        else:
                            print("\nError: get-latest-tweets requires both username and count arguments")
                            print("Usage: agent-action twitter get-latest-tweets <username> <count>")
                            return None
                    elif action_string == "post-tweet":
                        # Join all remaining arguments as the tweet message
                        kwargs['message'] = ' '.join(args)
                    elif action_string == "like-tweet":
                        if len(args) == 1:
                            kwargs['tweet_id'] = args[0]
                        else:
                            print("\nError: like-tweet requires exactly one tweet ID argument")
                            print("Usage: agent-action twitter like-tweet <tweet_id>")
                            return None
        
            # Call the action function with the arguments
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