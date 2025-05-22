uv sync --frozen
source .venv/bin/activate
python -c "import os; import duckdb; con = duckdb.connect(); con.execute(f\"SET http_proxy = '{os.getenv(\"HTTP_PROXY\")}'\"); con.execute(\"INSTALL 'sqlite';\")"
playwright install chromium
echo "source .venv/bin/activate" >> ~/.bashrc
