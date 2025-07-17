# Project Setup Instructions

## 1. Install pipx (if not already installed)
```fish
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

## 2. Install uv using pipx
```fish
pipx install uv
```

## 3. Create a new virtual environment with uv
```fish
uv venv .venv
```

## 4. Activate the virtual environment (fish shell)
```fish
source .venv/bin/activate.fish

```

## 5. Install the OpenAI package
```fish
uv pip install openai
```
