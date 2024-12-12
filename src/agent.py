import json
import random
import time
from src.connection_manager import ConnectionManager


class ZerePyAgent:
    def __init__(
            self, name: str,
            model: str,
            connection_manager: ConnectionManager,
            bio: str,
            moderated: bool=True,
            timeline_read_count: int=10,
            replies_per_tweet: int=5,
            loop_delay: int=30
    ):
        self.name = name
        self.model = model
        self.connection_manager = connection_manager
        self.bio = bio
        self.moderated = moderated

        # Behavior Parameters
        self.timeline_read_count = timeline_read_count
        self.replies_per_tweet = replies_per_tweet
        self.loop_delay = loop_delay

    def loop(self):
        # INITIAL DELAY
        time.sleep(2)
        print("Starting loop in 5 seconds...")
        for i in range(5):
            print(f"{i+1}...")
            time.sleep(2)

        # Main Loop
        while True:
            # READ TIMELINE AND REPLY
            print("\nREAD TWITTER TIMELINE")
            timeline_tweets = self.connection_manager.find_and_perform_action(
                action_string="read-timeline",
                connection_string="twitter",
                **{"count": self.timeline_read_count})
            for x, tweet in enumerate(timeline_tweets):
                # INTERACT WITH TWEET
                print("> INTERACT WITH TWEET:", tweet)
                action = random.choice([0, 1, 2])
                match action:
                    case 0:
                        print("-> LIKE TWEET")
                    case 1:
                        print("-> RETWEET TWEET")
                    case 2:
                        print("-> REPLY TO TWEET")

                # POST EVERY X INTERACTIONS
                if x % self.replies_per_tweet == 0:
                    print("-> POST ORIGINAL TWEET")

            # LOOP DELAY
            print(f"Delaying for {self.loop_delay} seconds...")
            time.sleep(self.loop_delay)

    def perform_action(self, action_string: str, connection_string: str, **kwargs):
            result = self.connection_manager.find_and_perform_action(action_string, connection_string, **kwargs)
            return result

    def to_dict(self):
        # TODO: Add all fields
        return {
            "name": self.name,
            "model": self.model,
            "bio": self.bio,
            "moderated": self.moderated
        }


def load_agent_from_file(agent_path: str, connection_manager: ConnectionManager) -> ZerePyAgent:
    try:
        # Get agent fields from json file
        agent_dict = json.load(open(agent_path, "r"))

        # Create agent object
        agent = ZerePyAgent(
            name=agent_dict["name"],
            model=agent_dict["model"],
            connection_manager=connection_manager,
            bio=agent_dict["bio"],
            moderated=agent_dict["moderated"]
        )
    except FileNotFoundError:
        raise FileNotFoundError(f"Agent file not found at path: {agent_path}")
    except KeyError:
        raise KeyError(f"Agent file is missing a required field.")
    except Exception as e:
        raise Exception(f"An error occurred while loading the agent: {e}")
    return agent


def create_agent_file_from_dict(agent_dict: dict):
    try:
        # Create agent file
        with open(f"agents/{agent_dict['name']}.json", "w") as file:
            # Save agent dict to json file
            json.dump(agent_dict, file, indent=4)
    except Exception as e:
        raise Exception(f"An error occurred while creating the agent file: {e}")
