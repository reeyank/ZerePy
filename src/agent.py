import json
import random
import time
import logging
from pathlib import Path
from src.connection_manager import ConnectionManager
from src.helpers import print_h_bar

REQUIRED_FIELDS = ["name", "bio", "traits", "examples", "loop_delay", "config"]

logger = logging.getLogger("agent")

class ZerePyAgent:
    def __init__(
            self,
            agent_name: str
    ):
        try:        
            agent_path =  Path("agents") / f"{agent_name}.json"
            agent_dict = json.load(open(agent_path, "r"))

            missing_fields = [field for field in REQUIRED_FIELDS if field not in agent_dict]
            if missing_fields:
                raise KeyError(f"Missing required fields: {', '.join(missing_fields)}")

            self.name=agent_dict["name"]
            self.bio=agent_dict["bio"]
            self.traits=agent_dict["traits"]
            self.examples=agent_dict["examples"]
            self.loop_delay=agent_dict["loop_delay"]
            self.connection_manager = ConnectionManager(agent_dict["config"])
        except Exception as e:
            logger.error("Encountered an error while initializing ZerePyAgent")
            raise e

    def perform_action(self, connection: str, action: str, **kwargs) -> None:
        return self.connection_manager.perform_action(connection, action, **kwargs)

    def loop(self):
        logger.info("\n🚀 Starting agent loop...")
        logger.info("Press Ctrl+C at any time to stop the loop.")
        print_h_bar() 

        time.sleep(2)
        logger.info("Starting loop in 5 seconds...")
        for i in range(5):
            logger.info(f"{i+1}...")
            time.sleep(2)

        # Main Loop
        while True:
            # READ TIMELINE AND REPLY
            logger.info("\nREAD TWITTER TIMELINE")
            timeline_tweets = self.connection_manager.perform_action(
                connection="twitter",
                action="read-timeline",
                **{"count": self.timeline_read_count})
            for x, tweet in enumerate(timeline_tweets):
                # INTERACT WITH TWEET
                logger.info("> INTERACT WITH TWEET:", tweet)
                action = random.choice([0, 1, 2])
                match action:
                    case 0:
                        logger.info("-> LIKE TWEET")
                    case 1:
                        logger.info("-> RETWEET TWEET")
                    case 2:
                        logger.info("-> REPLY TO TWEET")

                # POST EVERY X INTERACTIONS
                if x % self.replies_per_tweet == 0:
                    logger.info("-> POST ORIGINAL TWEET")

            # LOOP DELAY
            logger.info(f"Delaying for {self.loop_delay} seconds...")
            time.sleep(self.loop_delay)
