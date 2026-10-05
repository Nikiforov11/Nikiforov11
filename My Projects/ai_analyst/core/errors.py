class ToolError(Exception):
    """A problem the LLM can fix by changing its tool call
    (wrong column, impossible filter, no rows left...).

    Tools *raise* this internally; the @tool decorator turns it into a
    ToolResult with ok=False. Raising keeps the tool code linear and
    readable, while the LLM still always receives a structured result.
    """
