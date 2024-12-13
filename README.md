# ZerePy

We're building ZerePy, an open-source Python framework designed to let you deploy your own agents on X, powered by 
OpenAI or Anthropic LLMs.

ZerePy is built from a modularized version of the Zerebro backend. With ZerePy, you can launch your own agent with 
similar core functionality as Zerebro. For creative outputs, you'll need to fine-tune your own model.

## Installation

This project uses Poetry for dependency management. Here's how to get started:

1. First, install Poetry if you haven't already:
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Clone the repository:
```bash
git clone https://github.com/blorm-network/ZerePy.git
cd ZerePy
```

3. Install dependencies:
```bash
poetry install
```

This will create a virtual environment and install all required dependencies.

## Requirements

- Python 3.10 or higher
- Poetry 1.5 or higher

## Usage

1. Activate the virtual environment:
```bash
poetry shell
```

2. Run the application:
```bash
poetry run python main.py
```

------
Made with ♥ @Blorm.xyz
