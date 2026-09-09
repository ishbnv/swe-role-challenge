"""Frozen generic host adapter. Knows commands, never individual features."""

from collections.abc import Sequence

from core.runtime_spi import Command


class Cli:
    def __init__(self, commands: Sequence[Command]) -> None:
        self._commands = {command.name: command.run for command in commands}
        if len(self._commands) != len(commands):
            raise ValueError("duplicate command")

    def run(self, argv: Sequence[str]) -> str:
        if not argv or argv[0] not in self._commands:
            raise ValueError("unknown command")
        return self._commands[argv[0]](argv[1:])
