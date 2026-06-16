import os

from mafia.server.app import app


if __name__ == "__main__":
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        mcp_server=os.getenv("MAFIA_ENABLE_GRADIO_MCP", "1") != "0",
    )
