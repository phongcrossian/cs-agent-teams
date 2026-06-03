"""
ReplyMCP — the single customer-draft chokepoint (design §4a).

The ONLY path to emit a customer reply draft is the submit_reply(body, citations) tool
exposed by this MCP server. This chokepoint allows hooks to be the hard gate.
"""
