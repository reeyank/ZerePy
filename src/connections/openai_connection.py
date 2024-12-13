import logging
import os
from operator import truediv

from dotenv import load_dotenv, set_key
from src.connections.base_connection import BaseConnection
from openai import OpenAI
from typing import Dict, Any

# Configure module logger
logger = logging.getLogger(__name__)

class OpenAIConnectionError(Exception):
    """Base exception for OpenAI connection errors"""
    pass

class OpenAIConfigurationError(OpenAIConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class OpenAIAPIError(OpenAIConnectionError):
    """Raised when OpenAI API requests fail"""
    pass

class OpenAIConnection(BaseConnection):
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
        """Sets up OpenAI API authentication"""
        print("\n🤖 OPENAI API SETUP")

        # Check if already configured
        if self.is_configured(verbose=False):
            print("\nOpenAI API is already configured.")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return

        # Get API key
        print("\n📝 To get your OpenAI API credentials:")
        print("1. Go to https://platform.openai.com/account/api-keys")
        print("2. Create a new project or open an exiting one.")
        print("3. In your project settings, navigate to the API keys section and create a new API key")
        api_key = input("Enter your OpenAI API key: ")

        try:
            # Create .env file if it doesn't exist
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            # Save API key to .env file
            set_key('.env', 'OPENAI_API_KEY', api_key)

            print("\n✅ OpenAI API configuration successfully saved!")
            print("Your API key has been stored in the .env file.")

        except Exception as e:
            print(f"\n❌ An error occurred during setup: {str(e)}")
            return

    def is_configured(self, verbose=True) -> bool:
        """Checks if OpenAI API key is configured and valid"""
        if not os.path.exists('.env'):
            return False

        try:
            # Load env file variables
            load_dotenv()
            api_key = os.getenv('OPENAI_API_KEY')

            # Check if values present
            if not api_key:
                return False

            # Initialize the client
            client = OpenAI(api_key=api_key)
            
            # Try to make a minimal API call to validate the key
            models = [model.id for model in client.models.list().data]

            return True
            
        except Exception as e:
            if verbose:
                print("❌ There was an error validating your OpenAI credentials:", e)
            return False

    def perform_action(self, action_name: str, **kwargs) -> Any:
        """Implementation of abstract method from BaseConnection"""
        logger.debug(f"Performing action: {action_name}")
        if action_name in self.actions:
            return self.actions[action_name]["func"](**kwargs)
        error_msg = f"Unknown action: {action_name}"
        logger.error(error_msg)
        raise OpenAIConnectionError(error_msg)

    def generate_text(self, prompt : str, system_prompt : str, model : str, **kwargs):
        try:
            # Initialize the client
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            # Make the API call
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )

            # Return the response
            response_message = completion.choices[0].message.content
            return response_message
        except Exception as e:
            raise OpenAIAPIError(e)

    def check_model(self, model, **kwargs):
        try:
            # Make sure model exists
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            try:
                response = client.models.retrieve(model=model)

                # If we get here, the model exists
                return True
            except Exception:
                return False
        except Exception as e:
            raise OpenAIAPIError(e)

    def list_models(self, **kwargs):
        try:
            # Get available models
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.models.list().data
            model_ids = [model.id for model in response]
            fine_tuned_models = [model for model in response if model.owned_by in ["organization", "user", "organization-owner"]]

            # List available models
            logging.info("\nGPT MODELS:")
            logging.info("1. gpt-3.5-turbo")
            logging.info("2. gpt-4")
            logging.info("3. gpt-4-turbo")
            logging.info("4. gpt-4o")
            logging.info("5. gpt-4o-mini")
            if fine_tuned_models:
                logging.info("\nFINE-TUNED MODELS:")
                for i, model in enumerate(fine_tuned_models):
                    logging.info(f"{i+1}. {model.id}")

            return
        except Exception as e:
            raise OpenAIAPIError(e)
