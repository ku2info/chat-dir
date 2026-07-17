class ChatDirError(Exception):
    exit_code = 1
    hint = "Run with --debug for more detail."


class NotLoggedInError(ChatDirError):
    exit_code = 2
    hint = "Run: chat-dir login"


class NoChatsFoundError(ChatDirError):
    exit_code = 3
    hint = "Confirm the ChatGPT sidebar contains chat links, then retry."


class TimeoutError(ChatDirError):
    exit_code = 4
    hint = "Try --headed or increase --timeout-ms."


class OutputError(ChatDirError):
    exit_code = 5
    hint = "Check the output path and permissions."
