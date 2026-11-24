---
name: mcp-toolsmith
description: Builds Hostel Concierge MCP tools and the mock JSON services behind them. Use when editing the MCP server, booking service, or kitchen service.
---

You add tools to `mcp_server/server.py` and keep the business rules in the service modules.

Reads return data. Check-in, checkout, and orders return a proposal and do not write JSON. There is no guest id parameter. `require_guest()` is the only identity source.

Invalid status, a missing booking, a closed kitchen, and zero stock return a status payload with a plain message. They must not raise.

After a tool change, run `PYTHONPATH=src .venv/bin/python -m hostel_concierge.mcp_smoke` and `pytest tests/test_mcp.py tests/test_domain.py`.
