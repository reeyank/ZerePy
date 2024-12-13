import os
import sys
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from src.agent import load_agent_from_file
from src.helpers import print_h_bar
from src.connection_manager import ConnectionManager

@dataclass
class Command:
    """Dataclass to represent a CLI command"""
    name: str
    description: str
    tips: List[str]
    handler: Callable
    aliases: List[str] = None

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []

class ZerePyCLI:
    def __init__(self):
        self.agent = None
        self.connection_manager = ConnectionManager()
        
        # Create config directory if it doesn't exist
        self.config_dir = Path.home() / '.zerepy'
        self.config_dir.mkdir(exist_ok=True)
        
        # Initialize command registry
        self._initialize_commands()
        
        # Setup prompt toolkit components
        self._setup_prompt_toolkit()
        
        # Start CLI
        self.main_loop()

    def _initialize_commands(self) -> None:
        """Initialize all CLI commands"""
        self.commands: Dict[str, Command] = {}
        
        # Help command
        self._register_command(
            Command(
                name="help",
                description="Displays a list of all available commands, or help for a specific command.",
                tips=["Try 'help' to see available commands.",
                     "Try 'help {command}' to get more information about a specific command."],
                handler=self.help,
                aliases=['h', '?']
            )
        )
        
        # Agent action command
        self._register_command(
            Command(
                name="agent-action",
                description="Runs a single agent action.",
                tips=["Format: agent-action {connection} {action}",
                     "Use 'list-connections' to see available connections.",
                     "Use 'list-actions' to see available actions."],
                handler=self.agent_action,
                aliases=['action', 'run']
            )
        )
        
        # Agent loop command
        self._register_command(
            Command(
                name="agent-loop",
                description="Starts the current agent's autonomous behavior loop.",
                tips=["Press Ctrl+C to stop the loop"],
                handler=self.agent_loop,
                aliases=['loop', 'start']
            )
        )
        
        # List agents command
        self._register_command(
            Command(
                name="list-agents",
                description="Lists all available agents you have on file.",
                tips=["Agents are stored in the 'agents' directory",
                     "Use 'load-agent' to load an available agent"],
                handler=self.list_agents,
                aliases=['agents', 'ls-agents']
            )
        )
        
        # Load agent command
        self._register_command(
            Command(
                name="load-agent",
                description="Loads an agent from a file.",
                tips=["Format: load-agent {agent_name}",
                     "Use 'list-agents' to see available agents"],
                handler=self.load_agent,
                aliases=['load']
            )
        )
        
        # Create agent command
        self._register_command(
            Command(
                name="create-agent",
                description="Creates a new agent.",
                tips=["Follow the interactive wizard to create a new agent"],
                handler=self.create_agent,
                aliases=['new-agent', 'create']
            )
        )
        
        # List actions command
        self._register_command(
            Command(
                name="list-actions",
                description="Lists all available actions for the given connection.",
                tips=["Format: list-actions {connection}",
                     "Use 'list-connections' to see available connections"],
                handler=self.list_actions,
                aliases=['actions', 'ls-actions']
            )
        )
        
        # Configure connection command
        self._register_command(
            Command(
                name="configure-connection",
                description="Sets up a connection for API access.",
                tips=["Format: configure-connection {connection}",
                     "Follow the prompts to enter necessary credentials"],
                handler=self.configure_connection,
                aliases=['config', 'setup']
            )
        )
        
        # List connections command
        self._register_command(
            Command(
                name="list-connections",
                description="Lists all available connections.",
                tips=["Shows both configured and unconfigured connections"],
                handler=self.list_connections,
                aliases=['connections', 'ls-connections']
            )
        )
        
        # Exit command
        self._register_command(
            Command(
                name="exit",
                description="Exits the ZerePy CLI.",
                tips=["You can also use Ctrl+D to exit"],
                handler=self.exit,
                aliases=['quit', 'q']
            )
        )

    def _register_command(self, command: Command) -> None:
        """Register a command and its aliases"""
        self.commands[command.name] = command
        for alias in command.aliases:
            self.commands[alias] = command

    def _setup_prompt_toolkit(self) -> None:
        """Setup prompt toolkit components"""
        self.style = Style.from_dict({
            'prompt': 'ansicyan bold',
            'command': 'ansigreen',
            'error': 'ansired bold',
            'success': 'ansigreen bold',
            'warning': 'ansiyellow',
        })

        # Use FileHistory for persistent command history
        history_file = self.config_dir / 'history.txt'
        
        self.completer = WordCompleter(
            list(self.commands.keys()), 
            ignore_case=True,
            sentence=True
        )
        
        self.session = PromptSession(
            completer=self.completer,
            style=self.style,
            history=FileHistory(str(history_file))
        )

    def get_prompt_message(self) -> HTML:
        """Generate the prompt message based on current state"""
        agent_status = f"({self.agent.name})" if self.agent else "(no agent)"
        return HTML(f'<prompt>ZerePy-CLI</prompt> {agent_status} > ')

    def main_loop(self) -> None:
        """Main CLI loop"""
        self._print_welcome_message()
        
        while True:
            try:
                input_string = self.session.prompt(
                    self.get_prompt_message(),
                    style=self.style
                ).strip()

                if not input_string:
                    continue

                self._handle_command(input_string)
                print_h_bar()

            except KeyboardInterrupt:
                continue
            except EOFError:
                self.exit([])
            except Exception as e:
                print(f"\nUnexpected error: {e}")
                if os.getenv('ZEREPY_DEBUG'):
                    import traceback
                    traceback.print_exc()

    def _handle_command(self, input_string: str) -> None:
        """Parse and handle a command input"""
        input_list = input_string.split()
        command_string = input_list[0].lower()

        try:
            command = self.commands.get(command_string)
            if command:
                command.handler(input_list)
            else:
                self._handle_unknown_command(command_string)
        except Exception as e:
            print(f"\nError executing command: {e}")

    def _handle_unknown_command(self, command: str) -> None:
        """Handle unknown command with suggestions"""
        print(f"\nUnknown command: '{command}'")
        
        # Suggest similar commands using basic string similarity
        suggestions = self._get_command_suggestions(command)
        if suggestions:
            print("Did you mean one of these?")
            for suggestion in suggestions:
                print(f"  - {suggestion}")
        print("\nUse 'help' to see all available commands.")

    def _get_command_suggestions(self, command: str, max_suggestions: int = 3) -> List[str]:
        """Get command suggestions based on string similarity"""
        from difflib import get_close_matches
        return get_close_matches(command, self.commands.keys(), n=max_suggestions, cutoff=0.6)

    def _print_welcome_message(self) -> None:
        """Print welcome message and initial status"""
        print_h_bar()
        print("👋 Welcome to the ZerePy CLI!")
        print("Type 'help' for a list of commands.")
        self.list_connections([])
        print_h_bar()

    def help(self, input_list: List[str]) -> None:
        """Enhanced help command with better formatting"""
        if len(input_list) > 1:
            self._show_command_help(input_list[1])
        else:
            self._show_general_help()

    def _show_command_help(self, command_name: str) -> None:
        """Show help for a specific command"""
        command = self.commands.get(command_name)
        if not command:
            print(f"\nUnknown command: '{command_name}'")
            suggestions = self._get_command_suggestions(command_name)
            if suggestions:
                print("\nDid you mean one of these?")
                for suggestion in suggestions:
                    print(f"  - {suggestion}")
            return

        print(f"\nHelp for '{command.name}':")
        print(f"Description: {command.description}")
        
        if command.aliases:
            print(f"Aliases: {', '.join(command.aliases)}")
        
        if command.tips:
            print("\nTips:")
            for tip in command.tips:
                print(f"  - {tip}")

    def _show_general_help(self) -> None:
        """Show general help information"""
        print("\nAvailable Commands:")
        # Group commands by first letter for better organization
        commands_by_letter = {}
        for cmd_name, cmd in self.commands.items():
            # Only show main commands, not aliases
            if cmd_name == cmd.name:
                first_letter = cmd_name[0].upper()
                if first_letter not in commands_by_letter:
                    commands_by_letter[first_letter] = []
                commands_by_letter[first_letter].append(cmd)

        for letter in sorted(commands_by_letter.keys()):
            print(f"\n{letter}:")
            for cmd in sorted(commands_by_letter[letter], key=lambda x: x.name):
                print(f"  {cmd.name:<15} - {cmd.description}")

        if self.agent:
            print(f"\nCurrent Agent: {self.agent.name}")
        else:
            print("\nNo agent currently loaded")

    def exit(self, input_list: List[str]) -> None:
        """Exit the CLI gracefully"""
        print("\nGoodbye! 👋")
        sys.exit(0)

    def agent_action(self, input_list: List[str]) -> None:
        """Handle agent action command"""
        if self.agent is None:
            print("No agent is currently loaded. Use 'load-agent' to load an agent.")
            return

        if len(input_list) < 3:
            print("Please specify both a connection and an action.")
            print("Format: agent-action {connection} {action}")
            return

        connection_string = input_list[1]
        action_string = input_list[2]

        if not self.connection_manager.check_connection(connection_string):
            print(f"Connection '{connection_string}' is not configured.")
            print("Use 'configure-connection' to set it up.")
            return

        try:
            result = self.agent.perform_action(
                action_string=action_string,
                connection_string=connection_string,
                input_list=input_list
            )
            print("Result:", result)
        except Exception as e:
            print(f"Error running action: {e}")

    def agent_loop(self, input_list: List[str]) -> None:
        """Handle agent loop command"""
        if self.agent is None:
            print("No agent is currently loaded. Use 'load-agent' to load an agent.")
            return

        print("\n🚀 Starting agent loop...")
        print("Press Ctrl+C at any time to stop the loop.")
        print_h_bar()

        try:
            self.agent.loop()
        except KeyboardInterrupt:
            print("\n🛑 Agent loop stopped by user.")
        except Exception as e:
            print(f"\nError in agent loop: {e}")

    def list_agents(self, input_list: List[str]) -> None:
        """Handle list agents command"""
        print("\nAvailable Agents:")
        agents_dir = Path("agents")
        if not agents_dir.exists():
            print("No agents directory found.")
            return

        agents = list(agents_dir.glob("*.json"))
        if not agents:
            print("No agents found. Use 'create-agent' to create a new agent.")
            return

        for agent_file in sorted(agents):
            print(f"- {agent_file.stem}")

    def load_agent(self, input_list: List[str]) -> None:
        """Handle load agent command"""
        if len(input_list) < 2:
            print("Please specify an agent name.")
            print("Format: load-agent {agent_name}")
            print("Use 'list-agents' to see available agents.")
            return

        agent_name = input_list[1]
        try:
            agent_path = Path("agents") / f"{agent_name}.json"
            self.agent = load_agent_from_file(
                agent_path=str(agent_path),
                connection_manager=self.connection_manager
            )
            print(f"\n✅ Successfully loaded agent: {self.agent.name}")
        except FileNotFoundError:
            print(f"Agent file not found: {agent_name}")
            print("Use 'list-agents' to see available agents.")
        except KeyError as e:
            print(f"Invalid agent file: {e}")
        except Exception as e:
            print(f"Error loading agent: {e}")

    def create_agent(self, input_list: List[str]) -> None:
        """Handle create agent command"""
        print("\nℹ️ Agent creation wizard not implemented yet.")
        print("Please create agent JSON files manually in the 'agents' directory.")

    def list_actions(self, input_list: List[str]) -> None:
        """Handle list actions command"""
        if len(input_list) < 2:
            print("\nPlease specify a connection.")
            print("Format: list-actions {connection}")
            print("Use 'list-connections' to see available connections.")
            return

        connection_string = input_list[1]
        self.connection_manager.list_actions(connection_string=connection_string)

    def list_connections(self, input_list: List[str]) -> None:
        """Handle list connections command"""
        self.connection_manager.list_connections()

    def configure_connection(self, input_list: List[str]) -> None:
        """Handle configure connection command"""
        if len(input_list) < 2:
            print("\nPlease specify a connection to configure.")
            print("Format: configure-connection {connection}")
            print("Use 'list-connections' to see available connections.")
            return

        connection_string = input_list[1]
        self.connection_manager.configure_connection(connection_string=connection_string)
