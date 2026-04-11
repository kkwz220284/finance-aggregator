# Gemini CLI in Dev Container

This project uses the Gemini CLI for assistance. It is automatically installed in the development container.

## Authentication

When running in a development container, you must use the `NO_BROWSER=true` flag for authentication:

```bash
NO_BROWSER=true gemini auth login
```

Follow the link provided in the terminal to authorize the application with your Google account, and then copy the authorization code back into the terminal.
