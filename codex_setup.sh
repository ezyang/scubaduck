uv sync --frozen
source .venv/bin/activate
playwright install chromium
echo "source .venv/bin/activate" >> ~/.bashrc
