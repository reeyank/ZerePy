import logging
import os
from dotenv import load_dotenv, set_key
from src.connections.base_connection import BaseConnection
from anthropic import Anthropic
from typing import Dict, Any

# Configure module logger
logger = logging.getLogger(__name__)

class AnthropicConnectionError(Exception):
    """Base exception for Anthropic connection errors"""
    pass

class AnthropicConfigurationError(AnthropicConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class AnthropicAPIError(AnthropicConnectionError):
    """Raised when Anthropic API requests fail"""
    pass

class AnthropicConnection(BaseConnection):
    def __init__(self):
        super().__init__()
        self.actions={
            "generate-text": {
                "func": self.generate_text,
                "args": {
                    "prompt": "str",
                    "system_prompt": "str",
                    "model": "str"
                }
            },
            "check-model": {
                "func": self.check_model,
                "args": {"model": "str"}
            },
            "list-models": {
                "func": self.list_models,
                "args": {}
            }
        }

    def configure(self):
        """Sets up Anthropic API authentication"""
        print("\n🤖 ANTHROPIC API SETUP")

        # Check if already configured
        if self.is_configured(verbose=False):
            print("\nAnthropic API is already configured.")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return

        # Get API key
        print("\n📝 To get your Anthropic API credentials:")
        print("1. Go to https://console.anthropic.com/settings/keys")
        print("2. Create a new API key.")
        api_key = input("\nEnter your Anthropic API key: ")

        try:
            # Create .env file if it doesn't exist
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            # Save API key to .env file
            set_key('.env', 'ANTHROPIC_API_KEY', api_key)

            print("\n✅ Anthropic API configuration successfully saved!")
            print("Your API key has been stored in the .env file.")

        except Exception as e:
            print(f"\n❌ An error occurred during setup: {str(e)}")
            return

    def is_configured(self, verbose=True) -> bool:
        """Checks if Anthropic API key is configured and valid"""
        if not os.path.exists('.env'):
            return False

        try:
            # Load env file variables
            load_dotenv()
            api_key = os.getenv('ANTHROPIC_API_KEY')

            # Check if values present
            if not api_key:
                return False

            # Initialize the client
            client = Anthropic(api_key=api_key)
            
            # Try to make a minimal API call to validate the key
            client.models.list(limit=20)

            return True
            
        except Exception as e:
            if verbose:
                print("❌ There was an error validating your Anthropic credentials:", e)
            return False

    def is_llm_provider(self):
        return True

    def perform_action(self, action_name: str, **kwargs) -> Any:
        """Implementation of abstract method from BaseConnection"""
        logger.debug(f"Performing action: {action_name}")
        if action_name in self.actions:
            return self.actions[action_name]["func"](**kwargs)
        error_msg = f"Unknown action: {action_name}"
        logger.error(error_msg)
        raise AnthropicConnectionError(error_msg)

    def generate_text(self, prompt : str, system_prompt : str, model : str, **kwargs):
        try:
            # Initialize the client
            client = Anthropic()

            # Make the API call
            message = client.messages.create(
                model=model,
                max_tokens=1000,
                temperature=0,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )
            return message.content[0].text
        except Exception as e:
            raise AnthropicAPIError(e)

    def check_model(self, model, **kwargs):
        try:
            # Make sure model exists
            client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

            try:
                response = client.models.retrieve(model_id=model)

                # If we get here, the model exists
                return True
            except Exception:
                return False
        except Exception as e:
            raise AnthropicAPIError(e)

    def list_models(self, **kwargs):
        try:
            # Get available models
            client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            response = client.models.list().data
            model_ids = [model.id for model in response]
            #fine_tuned_models = [model for model in response if model.owned_by in ["organization", "user", "organization-owner"]]

            # List available models
            logging.info("\nCLAUDE MODELS:")
            for i, model in enumerate(model_ids):
                logging.info(f"{i+1}. {model}")
            #if fine_tuned_models:
                #logging.info("\nFINE-TUNED MODELS:")
                #for i, model in enumerate(fine_tuned_models):
                    #logging.info(f"{i+1}. {model.id}")
            return
        except Exception as e:
            raise AnthropicAPIError(e)
