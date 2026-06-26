# raphael-messaging

DMs, group channels, workspace channels

## API

- Prefix: `/v1/messaging`
- Port: `8089`
- Health: `GET /health`

## Events

_Published and consumed events documented in `openapi.yaml` and raphael-contracts._

## Development

```bash
uv sync
uv run uvicorn raphael_messaging.app:app --reload --port 8089
```

Part of the [Raphael Platform](https://github.com/hummingbird-labs) by HummingBird Labs.
