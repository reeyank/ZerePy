import json
import random
import time
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
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
            agent_path = Path("agents") / f"{agent_name}.json"
            agent_dict = json.load(open(agent_path, "r"))

            missing_fields = [field for field in REQUIRED_FIELDS if field not in agent_dict]
            if missing_fields:
                raise KeyError(f"Missing required fields: {', '.join(missing_fields)}")

            self.name = agent_dict["name"]
            self.bio = agent_dict["bio"]
            self.traits = agent_dict["traits"]
            self.examples = agent_dict["examples"]
            self.loop_delay = agent_dict["loop_delay"]  # This is in minutes
            self.connection_manager = ConnectionManager(agent_dict["config"])
            
            # Extract Twitter config
            twitter_config = next((config for config in agent_dict["config"] if config["name"] == "twitter"), None)
            if not twitter_config:
                raise KeyError("Twitter configuration is required")
                
            self.timeline_read_count = twitter_config.get("timeline_read_count", 10)
            self.interaction_weights = twitter_config.get("interaction_weights", {"like": 0.2, "reply": 0.8})
            self.self_reply_chance = twitter_config.get("self_reply_chance", 0.05)
            self.tweet_interval = twitter_config.get("tweet_interval", 900)
            
            # Get first available LLM provider and its model
            llm_providers = self.connection_manager.get_model_providers()
            logger.info(llm_providers)
            if not llm_providers:
                raise ValueError("No configured LLM provider found")
            self.model_provider = llm_providers[0]
            
            # Get the model from the provider's config
            provider_config = next((config for config in agent_dict["config"] if config["name"] == self.model_provider), None)
            if not provider_config or "model" not in provider_config:
                raise ValueError(f"No model configured for provider {self.model_provider}")
            self.model = provider_config["model"]
            
            # Load Twitter username for self-reply detection
            load_dotenv()
            self.username = os.getenv('TWITTER_USERNAME', '').lower()
            
            # Cache for system prompt
            self._system_prompt = None
            
        except Exception as e:
            logger.error("Encountered an error while initializing ZerePyAgent")
            raise e

    def _construct_system_prompt(self) -> str:
        """Construct the system prompt from agent configuration"""
        if self._system_prompt is None:
            prompt_parts = []
            prompt_parts.extend(self.bio)

            if self.traits:
                prompt_parts.append("\nYour key traits are:")
                prompt_parts.extend(f"- {trait}" for trait in self.traits)

            if self.examples:
                prompt_parts.append("\nHere are some examples of your style (Please avoid repeating any of these):")
                prompt_parts.extend(f"- {example}" for example in self.examples)

            self._system_prompt = "\n".join(prompt_parts)

        return self._system_prompt

    def prompt_llm(self, prompt: str, system_prompt: str = None) -> str:
        """Generate text using the configured LLM provider"""
        system_prompt = system_prompt or self._construct_system_prompt()
        
        return self.connection_manager.perform_action(
            connection_name=self.model_provider,
            action_name="generate-text",
            params=[prompt, system_prompt]
        )

    def loop(self):
        """Main agent loop for autonomous behavior"""
        logger.info("\n🚀 Starting agent loop...")
        logger.info("Press Ctrl+C at any time to stop the loop.")
        print_h_bar()

        time.sleep(2)
        logger.info("Starting loop in 5 seconds...")
        for i in range(5, 0, -1):
            logger.info(f"{i}...")
            time.sleep(1)

        last_tweet_time = 0

        try:
            while True:
                try:
                    # Check if it's time to post a new tweet
                    current_time = time.time()
                    if current_time - last_tweet_time >= self.tweet_interval:
                        logger.info("\n📝 GENERATING NEW TWEET")
                        print_h_bar()

                        prompt = "Generate an engaging tweet. Don't include hashtags, links or emojis. Keep it under 280 characters."
                        tweet_text = self.prompt_llm(prompt)

                        if tweet_text:
                            logger.info("\n🚀 Posting tweet:")
                            logger.info(f"'{tweet_text}'")
                            self.connection_manager.perform_action(
                                connection_name="twitter",
                                action_name="post-tweet",
                                params=[tweet_text]
                            )
                            last_tweet_time = current_time
                            logger.info("\n✅ Tweet posted successfully!")

                    # Read and interact with timeline
                    logger.info("\n👀 READING TIMELINE")
                    print_h_bar()

                    timeline_tweets = self.connection_manager.perform_action(
                        connection_name="twitter",
                        action_name="read-timeline",
                        params=[]
                    )

                    if timeline_tweets:
                        logger.info(f"\nFound {len(timeline_tweets)} tweets to process")
                        # Add delay between finding and processing tweets
                        time.sleep(30)
                        
                        # Process each tweet
                        for tweet in timeline_tweets:
                            tweet_id = tweet.get('id')
                            if not tweet_id:
                                continue

                            # Check if it's our own tweet using username
                            is_own_tweet = tweet.get('author_username', '').lower() == self.username
                            if is_own_tweet and random.random() > self.self_reply_chance:
                                continue

                            # Choose interaction based on weights
                            action = random.choices(
                                list(self.interaction_weights.keys()),
                                weights=list(self.interaction_weights.values())
                            )[0]

                            if action == 'like':
                                logger.info(f"\n❤️ LIKING TWEET: {tweet.get('text', '')[:50]}...")
                                self.connection_manager.perform_action(
                                    connection_name="twitter",
                                    action_name="like-tweet",
                                    params=[tweet_id]
                                )
                                logger.info("✅ Tweet liked successfully!")

                            elif action == 'reply':
                                logger.info(f"\n💬 GENERATING REPLY to: {tweet.get('text', '')[:50]}...")
                                
                                # Customize prompt based on whether it's a self-reply
                                base_prompt = f"Generate a friendly, engaging reply to this tweet: '{tweet.get('text')}'. Keep it under 280 characters."
                                if is_own_tweet:
                                    system_prompt = self._construct_system_prompt() + "\n\nYou are replying to your own previous tweet. Stay in character while building on your earlier thought."
                                    reply_text = self.prompt_llm(prompt=base_prompt, system_prompt=system_prompt)
                                else:
                                    reply_text = self.prompt_llm(prompt=base_prompt)

                                if reply_text:
                                    logger.info(f"\n🚀 Posting reply: '{reply_text}'")
                                    self.connection_manager.perform_action(
                                        connection_name="twitter",
                                        action_name="reply-to-tweet",
                                        params=[tweet_id, reply_text]
                                    )
                                    logger.info("✅ Reply posted successfully!")

                    # Delay between iterations (convert minutes to seconds)
                    logger.info(f"\n⏳ Waiting {self.loop_delay} minutes before next check...")
                    print_h_bar()
                    time.sleep(self.loop_delay * 60)  # Convert minutes to seconds

                except Exception as e:
                    logger.error(f"\n❌ Error in agent loop iteration: {e}")
                    logger.info(f"⏳ Waiting {self.loop_delay} minutes before retrying...")
                    time.sleep(self.loop_delay * 60)  # Convert minutes to seconds

        except KeyboardInterrupt:
            logger.info("\n🛑 Agent loop stopped by user.")
            return