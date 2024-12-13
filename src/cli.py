import os
import sys
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from src.agent import load_agent_from_file
from src.helpers import print_h_bar
from src.connection_manager import ConnectionManager

class ZerePyCLI:
    def __init__(self):
        # Initialize CLI parameters
        self.agent = None
        self.connection_manager = ConnectionManager()
        self.commands = {
            "help": {
                "command": "help",
                "description": "Displays a list of all available commands, or the help for a specific command.",
                "tips": ["Try 'help' to see available commands.",
                         "Try 'help {command}' to get more information about a specific command (e.g. 'help load_agent')."],
                "func": self.help
            },
            "agent_action": {
                "command": "agent_action",
                "description": "Runs a single agent action.",
                "tips": ["You must give the name of a connection and an action like so: 'agent_action {connection} {action}'.",
                         "You can use the 'list_connections' command to see all available connections.",
                         "You can use the 'list_actions' command to see all available actions for a given connection."],
                "func": self.agent_action
            },
            "agent_loop": {
                "command": "agent_loop",
                "description": "Starts the current agent's autonomous behavior loop.",
                "tips": [],
                "func": self.agent_loop
            },
            "list_agents": {
                "command": "list_agents",
                "description": "Lists all available agents you have on file.",
                "tips": ["You can load any available agent with the 'load_agent' command."],
                "func": self.list_agents
            },
            "load_agent": {
                "command": "load_agent",
                "description": "Loads an agent from a file.",
                "tips": ["You can list all available agents with the 'list_agents' command.",
                         "You do not need to specify the '.json' extension."],
                "func": self.load_agent
            },
            "exit": {
                "command": "exit",
                "description": "Exits the ZerePy CLI.",
                "tips": [],
                "func": self.exit
            },
            "create_agent": {
                "command": "create_agent",
                "description": "Creates a new agent.",
                "tips": [],
                "func": self.create_agent
            },
            "list_actions": {
                "command": "list_actions",
                "description": "Lists all available actions for the given connection.",
                "tips": [
                    "You must give the name of a connection like so: 'list_actions twitter'.",
                    "You can use the 'list_connections' command to see all available connections.",
                ],
                "func": self.list_actions
            },
            "configure_connection": {
                "command": "configure_connection",
                "description": "Sets up the given connection so that your agents can use the API.",
                "tips": [
                    "Each connection requires different credentials. You will be prompted for the necessary credentials.",
                    "You must give the name of a connection like so: 'configure_connection twitter'.",
                ],
                "func": self.configure_connection
            },
            "list_connections": {
                "command": "list_connections",
                "description": "Lists all available connections.",
                "tips": [],
                "func": self.list_connections
            }
        }

        # Initialize prompt toolkit style
        self.style = Style.from_dict({
            'prompt': 'ansicyan bold',
            'command': 'ansigreen',
            'error': 'ansired bold',
        })

        # Create command completer
        self.command_completer = WordCompleter(list(self.commands.keys()), ignore_case=True)
        
        # Initialize prompt session with history
        self.session = PromptSession(
            completer=self.command_completer,
            style=self.style,
            history=InMemoryHistory()
        )

        # Start CLI
        self.main_loop()

    def get_prompt_message(self):
        if self.agent is None:
            return HTML('<prompt>ZerePy-CLI</prompt> (no agent) > ')
        return HTML(f'<prompt>ZerePy-CLI</prompt> ({self.agent.name}) > ')

    def main_loop(self):
        # Send welcome message first
        print_h_bar()
        print("👋 Hello! Welcome to the ZerePy CLI!")
        # Check connections status once at startup
        self.list_connections([])
        print_h_bar()

        while True:
            try:
                # Get input using prompt_toolkit
                input_string = self.session.prompt(
                    self.get_prompt_message(),
                    style=self.style
                )

                # Get command from input
                input_list = input_string.split()
                if not input_list:  # Handle empty input
                    continue
                command_string = str(input_list[0])

                # Run command
                try:
                    # Match command string to a supported command
                    command_dict = self.commands[command_string]
                    command_func = command_dict["func"]
                    # Run command function
                    command_func(input_list)
                except KeyError:
                    print("\nUnknown command. Try 'help' to see available commands.")
                except Exception as e:
                    print(f"\nAn error occurred: {e}")

                # Add separator before next command
                print_h_bar()

            except KeyboardInterrupt:
                continue
            except EOFError:
                self.exit([])

    # [Rest of the methods remain the same as in the previous version]
    def help(self, input_list):
        help_arg_string = ""
        if len(input_list) > 1:
            help_arg_string = str(input_list[1])

        if help_arg_string != "":
            try:
                command_dict = self.commands[help_arg_string]
                command_description = command_dict["description"]
                print(f"\nHELP FOR '{help_arg_string}':")
                print(command_description)
                for tip in command_dict["tips"]:
                    print(f"- {tip}")
            except (IndexError, KeyError):
                print("Unknown command. Try 'help' to see available commands.")
            except Exception as e:
                print(f"An error occurred: {e}")
        else:
            print("\nAVAILABLE CLI COMMANDS:")
            for command in self.commands:
                print(f"- {command}")

            if self.agent is None:
                print("\nCURRENT AGENT: None")
            else:
                print(f"\nCURRENT AGENT: {self.agent.name}")

            print("\nDOCS: https://zerepy.com/docs")

    def exit(self, input_list):
        print("\nGoodbye! 👋")
        sys.exit(0)

    def agent_action(self, input_list):
        if self.agent is None:
            print("No agent is currently loaded. Use 'load_agent' to load an agent.")
            return

        if len(input_list) < 3:
            print("Please specify both a connection and an action. e.g. 'agent_action twitter post-tweet'")
            return

        connection_string = input_list[1]
        action_string = input_list[2]

        if not self.connection_manager.check_connection(connection_string):
            print(f"Connection '{connection_string}' is not configured. Use 'configure_connection' to set it up.")
            return

        try:
            result = self.agent.perform_action(
                action_string=action_string, 
                connection_string=connection_string, 
                input_list=input_list
            )
            print("RESULT:", result)
        except Exception as e:
            print(f"An error occurred while running the action: {e}")

    def agent_loop(self, input_list):
        if self.agent is None:
            print("No agent is currently loaded. Use 'load_agent' to load an agent.")
            return

        print("\n🚀 STARTING AGENT LOOP...")
        print("Press Ctrl+C at any time to stop the autonomous loop.")
        print_h_bar()

        try:
            self.agent.loop()
        except KeyboardInterrupt:
            print("\n🛑 AGENT LOOP STOPPED BY USER.")

    def list_agents(self, input_list):
        print("\nAVAILABLE AGENTS:")
        agents = 0
        for file in os.listdir("agents"):
            if file.endswith(".json"):
                print(f"- {file.removesuffix('.json')}")
                agents += 1

        if agents == 0:
            print("No agents found. Use 'create_agent' to create a new agent.")

    def load_agent(self, input_list):
        if len(input_list) < 2:
            print("Please specify an agent name. Use 'list_agents' to see available agents.")
            return

        try:
            self.agent = load_agent_from_file(
                agent_path=f"agents/{input_list[1].removesuffix('.json')}.json",
                connection_manager=self.connection_manager
            )
            print(f"\n✅ SUCCESSFULLY LOADED AGENT: {self.agent.name}")
        except FileNotFoundError:
            print("Agent file not found. Use 'list_agents' to see available agents.")
        except KeyError:
            print("Agent file is missing a required field.")
        except Exception as e:
            print(f"An error occurred while loading the agent: {e}")

    def create_agent(self, input_list):
        # TODO: Implement interactive agent creation wizard
        pass

    def list_actions(self, input_list):
        if len(input_list) < 2:
            print("\nPlease specify a connection. Use 'list_connections' to see supported connections.")
            return
        self.connection_manager.list_actions(connection_string=input_list[1])

    def list_connections(self, input_list):
        self.connection_manager.list_connections()

    def configure_connection(self, input_list):
        if len(input_list) < 2:
            print("\nPlease specify a connection to configure. Use 'list_connections' to see supported connections.")
            return
        self.connection_manager.configure_connection(connection_string=input_list[1])