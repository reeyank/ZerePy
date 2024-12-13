
# ZerePy Agent Template

A starting point for building your own AI agents on X (formerly Twitter), powered by OpenAI or Anthropic LLMs.

## Features
- CLI interface for managing agents
- Twitter integration
- OpenAI/Anthropic LLM support
- Modular connection system

## Getting Started

1. Fork this template
2. Install dependencies by clicking Run
3. Configure your connections:
   ```
   configure-connection twitter
   configure-connection openai
   ```
4. Load the example agent:
   ```
   load-agent example
   ```
5. Start your agent:
   ```
   agent-loop
   ```

## Creating Your Own Agent

Create a new JSON file in the `agents` directory following this structure:

```json
{
  "name": "YourAgent",
  "model": "gpt-3.5-turbo",
  "bio": "Your agent's description",
  "moderated": true
}
```

## License
MIT License

Made with ♥ @Blorm.xyz
