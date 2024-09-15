# muscpy

A Discord music bot powered by Python, FFmpeg, and yt-dlp.

# ToC
* [Usage](#usage)
* [Known Issues](#known-issues)
* [Quality of Life Issues](#quality-of-life-issues)

## Usage

1. **Clone the repository** using Git or download it as an archive:
   ```bash
   git clone https://github.com/mal1kc/muscpy
   ```

2. **Set up the `BOT_TOKEN` variable** in the `.env` file.  
   Example `.env` file:
   ```bash
   DCBOT_TOKEN="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   ```

### Starting the Bot

#### Using Rye

Run the bot from the directory where `pyproject.toml` is located:
```bash
rye sync
rye run python -m muscpy
```

#### Using Virtualenv

1. **Create a virtual environment**:
   ```bash
   virtualenv .venv
   ```
2. **Install dependencies**:
   - **On Windows**:
     ```powershell
     # Install dependencies
     .\.venv\Scripts\pip.exe install -r .\requirements.txt
     # Install muscpy
     .\.venv\Scripts\pip.exe install .
     ```
   - **On Linux**:
     ```bash
     # Install dependencies
     ./.venv/bin/pip install -r ./requirements.txt
     # Install muscpy
     ./.venv/bin/pip install .
     ```
3. **Run the bot**:
   - **For Windows**:
     ```powershell
     .\.venv\Scripts\python.exe start_muscpy.py
     ```
   - **For Linux**:
     ```bash
     ./.venv/bin/python start_muscpy.py
     ```
## Known Issues

- Durations may be in an incorrect format (can be overtime).
- Issues related to YouTube request limits (not planned to be fixed).

## Quality of Life Issues

- Double join VC messages.
- Some unneeded messages.
- Some messages may be unclear.

