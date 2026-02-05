"""Launcher for the Flask web app.

Keeps the old `python3 app.py` workflow after reorganizing folders.
"""

from web.app import app


if __name__ == "__main__":
    # Delegate to the real Flask app
    app.run(debug=True)
