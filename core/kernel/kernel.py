"""Kernel implementation: validate declarations, plan artifact steps, assemble, verify, freeze.

Kernel is single-use. boot(modules) returns App only after complete success.
The implementation knows no feature or executable host. Kernel alone supplies
the built-in INVOKER artifact as an already-satisfied planning input; its per-boot
callable must remain disabled until readiness and after failed boot.
"""

import heapq
from collections.abc import Callable, Sequence
from typing import Any, cast

from core.runtime_spi import (
    App,
    ArtifactKey,
    BootContext,
    Command,
    Invoker,
    Module,
    Operation,
    Step,
)
from core.runtime_spi.operations import INVOKER


class _App(App):
    def __init__(self, commands: tuple[Command, ...], invoker: Invoker) -> None:
        self._commands = commands
        self._invoker = invoker

    @property
    def commands(self) -> tuple[Command, ...]:
        return self._commands

    def invoke[I, O](self, operation: Operation[I, O], input: I) -> O:
        return self._invoker(operation, input)


class _KernelInvoker(Invoker):
    def __init__(self) -> None:
        self._is_ready: bool = False
        self._handlers: dict[Operation[Any, Any], Callable[[Any], Any]] = {}

    def enable(self) -> None:
        self._is_ready = True

    def disable(self) -> None:
        self._is_ready = False

    def register_handler(
        self, operation: Operation[Any, Any], handler: Callable[[Any], Any]
    ) -> None:
        if operation in self._handlers:
            raise ValueError(f"Operation '{operation.name}' has already been bound by a step")
        self._handlers[operation] = handler

    def has_handler(self, operation: Operation[Any, Any]) -> bool:
        return operation in self._handlers

    def __call__[I, O](self, operation: Operation[I, O], input: I) -> O:
        if not self._is_ready:
            raise RuntimeError("Invoker is disabled: boot has not succeeded or has failed")
        if operation not in self._handlers:
            raise ValueError(f"Unknown operation: {operation.name}")
        handler = self._handlers[operation]
        return cast(O, handler(input))


_Invoker = _KernelInvoker


class _StepBootContext(BootContext):
    def __init__(
        self,
        step: Step,
        module: Module,
        artifacts: dict[ArtifactKey[Any], Any],
        invoker: _KernelInvoker,
        commands: list[Command],
        command_names: set[str],
    ) -> None:
        self._step = step
        self._module = module
        self._artifacts = artifacts
        self._invoker = invoker
        self._commands = commands
        self._command_names = command_names
        self._provided_by_step: set[ArtifactKey[Any]] = set()
        self._active: bool = True

    def disable(self) -> None:
        self._active = False

    def missing_outputs(self) -> frozenset[ArtifactKey[Any]]:
        return self._step.provides - self._provided_by_step

    def require[T](self, key: ArtifactKey[T]) -> T:
        if not self._active:
            raise RuntimeError(f"BootContext for step '{self._step.name}' is disabled")
        if key not in self._step.requires:
            raise ValueError(
                f"Step '{self._step.name}' did not declare requirement for artifact '{key.name}'"
            )
        if key not in self._artifacts:
            raise KeyError(f"Artifact '{key.name}' is not available")
        return cast(T, self._artifacts[key])

    def provide[T](self, key: ArtifactKey[T], value: T) -> None:
        if not self._active:
            raise RuntimeError(f"BootContext for step '{self._step.name}' is disabled")
        if key not in self._step.provides:
            raise ValueError(
                f"Step '{self._step.name}' did not declare output for artifact '{key.name}'"
            )
        if key in self._provided_by_step:
            raise ValueError(
                f"Step '{self._step.name}' duplicate provide call for artifact '{key.name}'"
            )
        self._artifacts[key] = value
        self._provided_by_step.add(key)

    def bind[I, O](self, operation: Operation[I, O], handler: Callable[[I], O]) -> None:
        if not self._active:
            raise RuntimeError(f"BootContext for step '{self._step.name}' is disabled")
        if operation not in self._module.operations:
            raise ValueError(
                f"Module '{self._module.name}' does not own operation '{operation.name}'"
            )
        self._invoker.register_handler(operation, handler)

    def contribute(self, command: Command) -> None:
        if not self._active:
            raise RuntimeError(f"BootContext for step '{self._step.name}' is disabled")
        if command.name in self._command_names:
            raise ValueError(f"Duplicate command name: '{command.name}'")
        self._command_names.add(command.name)
        self._commands.append(command)


class Kernel:
    def __init__(self) -> None:
        self._has_booted: bool = False

    def boot(self, modules: Sequence[Module]) -> App:
        if self._has_booted:
            raise RuntimeError("Kernel can only boot once")
        self._has_booted = True

        invoker = _KernelInvoker()
        contexts: list[_StepBootContext] = []

        try:
            # 1. Whole-plan validation
            self._validate_modules(modules)
            sorted_steps, step_module_map = self._plan_steps(modules)

            # 2. Setup execution
            artifacts: dict[ArtifactKey[Any], Any] = {INVOKER: invoker}
            commands: list[Command] = []
            command_names: set[str] = set()

            for step in sorted_steps:
                mod = step_module_map[step]
                ctx = _StepBootContext(
                    step=step,
                    module=mod,
                    artifacts=artifacts,
                    invoker=invoker,
                    commands=commands,
                    command_names=command_names,
                )
                contexts.append(ctx)
                step.run(ctx)

                missing = ctx.missing_outputs()
                if missing:
                    names = {k.name for k in missing}
                    raise ValueError(
                        f"Step '{step.name}' finished without providing declared outputs: {names}"
                    )

            # 3. Check all declared operations have bound handlers
            for mod in modules:
                for op in mod.operations:
                    if not invoker.has_handler(op):
                        raise ValueError(
                            f"Operation '{op.name}' declared by module '{mod.name}' was not bound"
                        )

            # 4. Successful boot: disable contexts and activate invoker
            for ctx in contexts:
                ctx.disable()
            invoker.enable()

            return _App(commands=tuple(commands), invoker=invoker)

        except Exception:
            for ctx in contexts:
                ctx.disable()
            invoker.disable()
            raise

    def _validate_modules(self, modules: Sequence[Module]) -> None:
        # Module name uniqueness
        seen_module_names: set[str] = set()
        for mod in modules:
            if mod.name in seen_module_names:
                raise ValueError(f"Duplicate module name: '{mod.name}'")
            seen_module_names.add(mod.name)

        # Step name uniqueness globally
        seen_step_names: set[str] = set()
        for mod in modules:
            for step in mod.steps:
                if step.name in seen_step_names:
                    raise ValueError(f"Duplicate step name: '{step.name}'")
                seen_step_names.add(step.name)

        # Check rule 5: no step may provide INVOKER or any key named "runtime.invoker"
        for mod in modules:
            for step in mod.steps:
                for prov in step.provides:
                    if prov is INVOKER or prov.name == "runtime.invoker":
                        raise ValueError(
                            f"Step '{step.name}' cannot provide INVOKER or key named 'runtime.invoker'"
                        )

        # ArtifactKey namespace & identity check
        artifact_keys_by_name: dict[str, ArtifactKey[Any]] = {INVOKER.name: INVOKER}
        for mod in modules:
            for step in mod.steps:
                for key in step.requires | step.provides:
                    if key.name in artifact_keys_by_name:
                        if artifact_keys_by_name[key.name] is not key:
                            raise ValueError(
                                f"Distinct ArtifactKey objects share name '{key.name}'"
                            )
                    else:
                        artifact_keys_by_name[key.name] = key

        # Operation namespace & identity check
        operations_by_name: dict[str, Operation[Any, Any]] = {}
        for mod in modules:
            for op in mod.operations | mod.uses:
                if op.name in operations_by_name:
                    if operations_by_name[op.name] is not op:
                        raise ValueError(f"Distinct Operation objects share name '{op.name}'")
                else:
                    operations_by_name[op.name] = op

        # Operation ownership: exactly one owner per operation
        owned_operations: set[Operation[Any, Any]] = set()
        for mod in modules:
            for op in mod.operations:
                if op in owned_operations:
                    raise ValueError(
                        f"Duplicate operation owner for '{op.name}' in module '{mod.name}'"
                    )
                owned_operations.add(op)

        # Module uses check: each used operation must be declared by some module
        for mod in modules:
            for op in mod.uses:
                if op not in owned_operations:
                    raise ValueError(f"Module '{mod.name}' uses undeclared operation '{op.name}'")

        # Artifact providers: single provider for each artifact, and all requires must have a provider
        providers_by_key: dict[ArtifactKey[Any], Step] = {}
        for mod in modules:
            for step in mod.steps:
                for prov in step.provides:
                    if prov in providers_by_key:
                        raise ValueError(
                            f"Duplicate provider for artifact '{prov.name}': "
                            f"provided by both '{providers_by_key[prov].name}' and '{step.name}'"
                        )
                    providers_by_key[prov] = step

        for mod in modules:
            for step in mod.steps:
                for req in step.requires:
                    if req is INVOKER:
                        continue
                    if req not in providers_by_key:
                        raise ValueError(
                            f"Missing provider for artifact '{req.name}' required by step '{step.name}'"
                        )

    def _plan_steps(self, modules: Sequence[Module]) -> tuple[list[Step], dict[Step, Module]]:
        all_steps: list[Step] = []
        step_module_map: dict[Step, Module] = {}
        provider_by_key: dict[ArtifactKey[Any], Step] = {}

        for mod in modules:
            for step in mod.steps:
                all_steps.append(step)
                step_module_map[step] = mod
                for prov in step.provides:
                    provider_by_key[prov] = step

        # Build DAG
        in_degree: dict[Step, int] = {s: 0 for s in all_steps}
        dependents: dict[Step, list[Step]] = {s: [] for s in all_steps}

        for step in all_steps:
            predecessors: set[Step] = set()
            for req in step.requires:
                if req is INVOKER:
                    continue
                dep_step = provider_by_key[req]
                if dep_step is step:
                    raise ValueError(
                        f"Step '{step.name}' requires its own provided artifact '{req.name}'"
                    )
                predecessors.add(dep_step)

            in_degree[step] = len(predecessors)
            for dep in predecessors:
                dependents[dep].append(step)

        # Kahn's topological sort with deterministic tie-breaking by step name
        ready_heap: list[tuple[str, Step]] = [(s.name, s) for s in all_steps if in_degree[s] == 0]
        heapq.heapify(ready_heap)
        sorted_steps: list[Step] = []

        while ready_heap:
            _, current = heapq.heappop(ready_heap)
            sorted_steps.append(current)
            for neighbor in dependents[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    heapq.heappush(ready_heap, (neighbor.name, neighbor))

        if len(sorted_steps) != len(all_steps):
            raise ValueError("Artifact dependency cycle detected")

        return sorted_steps, step_module_map
