"""Unit tests for Kernel runtime assembly, validation, planning, and execution.

Covers all rules:
- Whole-plan validation before step execution (duplicates, cycles, missing providers/operations, identity checks)
- Topological order and deterministic tie-breaking for independent steps
- StepBootContext isolation (scoped require, scoped provide, complete provides check, unowned bind, duplicate bind, duplicate command)
- Single-use Kernel and lockdown on failure
- Context disabling after boot (successful or failed)
- Invoker lifecycle (disabled during boot and after failure, enabled upon readiness, unknown op handling)
- App contract (immutable commands tuple, delegation to invoker, no artifact leakage)
- Mutual operation dependencies (valid when no artifact cycle)
"""

import unittest
from typing import Any

from core.kernel.kernel import Kernel
from core.runtime_spi import ArtifactKey, BootContext, Command, Module, Operation, Step
from core.runtime_spi.operations import INVOKER


class KernelTests(unittest.TestCase):
    # =========================================================================
    # A. Whole-Plan Validation (runs before ANY step executes)
    # =========================================================================

    def test_validation_runs_before_any_step_executes(self) -> None:
        executed_steps: list[str] = []

        def s1(ctx: BootContext) -> None:
            executed_steps.append("s1")

        k_missing = ArtifactKey("missing", str)
        s_ok = Step("s_ok", s1)
        s_bad = Step("s_bad", lambda ctx: None, requires=frozenset({k_missing}))

        mod1 = Module(name="mod1", steps=(s_ok,))
        mod2 = Module(name="mod2", steps=(s_bad,))

        with self.assertRaises(ValueError):
            Kernel().boot([mod1, mod2])

        # s_ok must NOT have executed because validation runs before any step
        self.assertEqual(executed_steps, [])

    def test_reject_duplicate_module_names(self) -> None:
        mod1 = Module(name="duplicate_mod", steps=())
        mod2 = Module(name="duplicate_mod", steps=())
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod1, mod2])
        self.assertIn("Duplicate module name", str(cm.exception))

    def test_reject_duplicate_step_names_within_same_module(self) -> None:
        s1 = Step("dup_step", lambda ctx: None)
        s2 = Step("dup_step", lambda ctx: None)
        mod = Module(name="mod", steps=(s1, s2))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("Duplicate step name", str(cm.exception))

    def test_reject_duplicate_step_names_across_different_modules(self) -> None:
        s1 = Step("shared_step_name", lambda ctx: None)
        s2 = Step("shared_step_name", lambda ctx: None)
        mod1 = Module(name="mod1", steps=(s1,))
        mod2 = Module(name="mod2", steps=(s2,))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod1, mod2])
        self.assertIn("Duplicate step name", str(cm.exception))

    def test_reject_distinct_artifact_keys_sharing_name(self) -> None:
        k1: ArtifactKey[str] = ArtifactKey("same.key", str)
        k2: ArtifactKey[str] = ArtifactKey("same.key", str)
        self.assertIsNot(k1, k2)

        s1 = Step("s1", lambda ctx: ctx.provide(k1, "v1"), provides=frozenset({k1}))
        s2 = Step("s2", lambda ctx: ctx.provide(k2, "v2"), provides=frozenset({k2}))
        mod = Module(name="mod", steps=(s1, s2))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("Distinct ArtifactKey objects share name", str(cm.exception))

    def test_reject_distinct_operations_sharing_name(self) -> None:
        op1 = Operation("same.op", str, str)
        op2 = Operation("same.op", str, str)
        self.assertIsNot(op1, op2)

        mod1 = Module(name="mod1", steps=(), operations=frozenset({op1}))
        mod2 = Module(name="mod2", steps=(), operations=frozenset({op2}))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod1, mod2])
        self.assertIn("Distinct Operation objects share name", str(cm.exception))

    def test_independent_namespaces_artifact_and_operation(self) -> None:
        # ArtifactKey and Operation sharing the same name string is completely valid
        shared_name = "common.identity"
        key = ArtifactKey(shared_name, str)
        op = Operation(shared_name, str, str)

        def step_run(ctx: BootContext) -> None:
            ctx.provide(key, "data")
            ctx.bind(op, lambda x: f"{x}-handled")

        mod = Module(
            name="mod",
            steps=(Step("step", step_run, provides=frozenset({key})),),
            operations=frozenset({op}),
        )
        app = Kernel().boot([mod])
        self.assertEqual(app.invoke(op, "in"), "in-handled")

    def test_reject_step_providing_invoker(self) -> None:
        s = Step("s", lambda ctx: None, provides=frozenset({INVOKER}))
        mod = Module(name="mod", steps=(s,))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("cannot provide INVOKER", str(cm.exception))

    def test_reject_step_providing_key_named_runtime_invoker(self) -> None:
        fake_invoker: ArtifactKey[object] = ArtifactKey("runtime.invoker", object)
        s = Step("s", lambda ctx: None, provides=frozenset({fake_invoker}))
        mod = Module(name="mod", steps=(s,))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("runtime.invoker", str(cm.exception))

    def test_reject_step_requiring_fake_runtime_invoker(self) -> None:
        fake_invoker: ArtifactKey[object] = ArtifactKey("runtime.invoker", object)
        s = Step("s", lambda ctx: None, requires=frozenset({fake_invoker}))
        mod = Module(name="mod", steps=(s,))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("runtime.invoker", str(cm.exception))

    def test_reject_duplicate_operation_owners(self) -> None:
        op = Operation("shared.op", str, str)
        mod1 = Module(name="mod1", steps=(), operations=frozenset({op}))
        mod2 = Module(name="mod2", steps=(), operations=frozenset({op}))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod1, mod2])
        self.assertIn("Duplicate operation owner", str(cm.exception))

    def test_reject_missing_used_operation(self) -> None:
        op = Operation("ghost.op", str, str)
        mod = Module(name="mod", steps=(), uses=frozenset({op}))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("uses undeclared operation", str(cm.exception))

    def test_reject_missing_artifact_provider(self) -> None:
        k = ArtifactKey("unprovided.key", str)
        s = Step("s", lambda ctx: None, requires=frozenset({k}))
        mod = Module(name="mod", steps=(s,))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("Missing provider for artifact", str(cm.exception))

    def test_reject_duplicate_artifact_providers(self) -> None:
        k = ArtifactKey("colliding.key", str)
        s1 = Step("s1", lambda ctx: ctx.provide(k, "1"), provides=frozenset({k}))
        s2 = Step("s2", lambda ctx: ctx.provide(k, "2"), provides=frozenset({k}))
        mod = Module(name="mod", steps=(s1, s2))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("Duplicate provider for artifact", str(cm.exception))

    def test_reject_step_requiring_own_output(self) -> None:
        k = ArtifactKey("self.dep", str)
        s = Step("s", lambda ctx: None, requires=frozenset({k}), provides=frozenset({k}))
        mod = Module(name="mod", steps=(s,))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("requires its own provided artifact", str(cm.exception))

    def test_reject_artifact_dependency_cycle_two_steps(self) -> None:
        k1 = ArtifactKey("k1", str)
        k2 = ArtifactKey("k2", str)
        s1 = Step(
            "s1",
            lambda ctx: None,
            requires=frozenset({k2}),
            provides=frozenset({k1}),
        )
        s2 = Step(
            "s2",
            lambda ctx: None,
            requires=frozenset({k1}),
            provides=frozenset({k2}),
        )
        mod = Module(name="mod", steps=(s1, s2))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("cycle", str(cm.exception).lower())

    def test_reject_artifact_dependency_cycle_three_steps(self) -> None:
        k1 = ArtifactKey("k1", str)
        k2 = ArtifactKey("k2", str)
        k3 = ArtifactKey("k3", str)
        s1 = Step("s1", lambda ctx: None, requires=frozenset({k3}), provides=frozenset({k1}))
        s2 = Step("s2", lambda ctx: None, requires=frozenset({k1}), provides=frozenset({k2}))
        s3 = Step("s3", lambda ctx: None, requires=frozenset({k2}), provides=frozenset({k3}))
        mod = Module(name="mod", steps=(s1, s2, s3))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("cycle", str(cm.exception).lower())

    # =========================================================================
    # B. Topological Execution and Deterministic Tie-Breaking
    # =========================================================================

    def test_topological_execution_order(self) -> None:
        k_a = ArtifactKey("a", int)
        k_b = ArtifactKey("b", int)
        order: list[str] = []

        def run_step1(ctx: BootContext) -> None:
            order.append("step1")
            ctx.provide(k_a, 10)

        def run_step2(ctx: BootContext) -> None:
            order.append("step2")
            val = ctx.require(k_a)
            ctx.provide(k_b, val * 2)

        def run_step3(ctx: BootContext) -> None:
            order.append("step3")
            ctx.require(k_b)

        mod = Module(
            name="mod",
            steps=(
                Step("step3", run_step3, requires=frozenset({k_b})),
                Step("step2", run_step2, requires=frozenset({k_a}), provides=frozenset({k_b})),
                Step("step1", run_step1, provides=frozenset({k_a})),
            ),
        )

        Kernel().boot([mod])
        self.assertEqual(order, ["step1", "step2", "step3"])

    def test_deterministic_execution_for_independent_steps(self) -> None:
        order: list[str] = []

        def make_step(name: str) -> Step:
            return Step(name, lambda ctx, n=name: order.append(n))

        # Independent steps in reverse order
        s_z = make_step("z_step")
        s_m = make_step("m_step")
        s_a = make_step("a_step")

        mod = Module(name="mod", steps=(s_z, s_m, s_a))
        Kernel().boot([mod])
        # Deterministic sorting by name ensures alphabetical execution
        self.assertEqual(order, ["a_step", "m_step", "z_step"])

    def test_mutual_operation_dependencies_allowed(self) -> None:
        # Module A uses B's operation; Module B uses A's operation.
        # This is strictly legal and must not produce a cycle error.
        op_a = Operation("op_a", str, str)
        op_b = Operation("op_b", str, str)

        def step_a_run(ctx: BootContext) -> None:
            ctx.bind(op_a, lambda s: f"A({s})")

        def step_b_run(ctx: BootContext) -> None:
            ctx.bind(op_b, lambda s: f"B({s})")

        mod_a = Module(
            name="mod_a",
            steps=(Step("step_a", step_a_run),),
            operations=frozenset({op_a}),
            uses=frozenset({op_b}),
        )
        mod_b = Module(
            name="mod_b",
            steps=(Step("step_b", step_b_run),),
            operations=frozenset({op_b}),
            uses=frozenset({op_a}),
        )

        app = Kernel().boot([mod_a, mod_b])
        self.assertEqual(app.invoke(op_a, "test"), "A(test)")
        self.assertEqual(app.invoke(op_b, "test"), "B(test)")

    # =========================================================================
    # C. Step Context Scoping (Artifact Access & Completeness)
    # =========================================================================

    def test_step_reading_undeclared_requirement_fails(self) -> None:
        k1 = ArtifactKey("k1", str)
        k2 = ArtifactKey("k2", str)

        def s1(ctx: BootContext) -> None:
            ctx.provide(k1, "v1")
            ctx.provide(k2, "v2")

        def s2(ctx: BootContext) -> None:
            ctx.require(k2)  # k2 is available, but NOT declared in s2.requires

        mod = Module(
            name="mod",
            steps=(
                Step("s1", s1, provides=frozenset({k1, k2})),
                Step("s2", s2, requires=frozenset({k1})),
            ),
        )
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("did not declare requirement", str(cm.exception))

    def test_step_reading_invoker_without_declaring_requirement_fails(self) -> None:
        def s(ctx: BootContext) -> None:
            ctx.require(INVOKER)  # INVOKER is in Kernel, but NOT in s.requires

        mod = Module(name="mod", steps=(Step("s", s, requires=frozenset()),))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("did not declare requirement", str(cm.exception))

    def test_step_writing_undeclared_output_fails(self) -> None:
        k = ArtifactKey("k", str)

        def s(ctx: BootContext) -> None:
            ctx.provide(k, "v")

        mod = Module(name="mod", steps=(Step("s", s, provides=frozenset()),))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("did not declare output", str(cm.exception))

    def test_step_duplicate_provide_fails(self) -> None:
        k = ArtifactKey("k", str)

        def s(ctx: BootContext) -> None:
            ctx.provide(k, "v1")
            ctx.provide(k, "v2")

        mod = Module(name="mod", steps=(Step("s", s, provides=frozenset({k})),))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("duplicate provide call", str(cm.exception))

    def test_step_missing_declared_output_fails(self) -> None:
        k = ArtifactKey("k", str)

        def s(ctx: BootContext) -> None:
            pass  # did not provide k

        mod = Module(name="mod", steps=(Step("s", s, provides=frozenset({k})),))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("without providing declared outputs", str(cm.exception))

    def test_artifact_value_can_be_none(self) -> None:
        k_none: ArtifactKey[None] = ArtifactKey("none.key", type(None))
        received: list[Any] = []

        def s1(ctx: BootContext) -> None:
            ctx.provide(k_none, None)

        def s2(ctx: BootContext) -> None:
            val = ctx.require(k_none)
            received.append(val)

        mod = Module(
            name="mod",
            steps=(
                Step("s1", s1, provides=frozenset({k_none})),
                Step("s2", s2, requires=frozenset({k_none})),
            ),
        )
        Kernel().boot([mod])
        self.assertEqual(received, [None])

    # =========================================================================
    # D. Operation Binding & Commands
    # =========================================================================

    def test_step_binding_unowned_operation_fails(self) -> None:
        op = Operation("foreign.op", str, str)

        def s(ctx: BootContext) -> None:
            ctx.bind(op, lambda x: x)

        mod = Module(name="mod", steps=(Step("s", s),), operations=frozenset())
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("does not own operation", str(cm.exception))

    def test_step_duplicate_operation_bind_fails(self) -> None:
        op = Operation("op", str, str)

        def s1(ctx: BootContext) -> None:
            ctx.bind(op, lambda x: x)

        def s2(ctx: BootContext) -> None:
            ctx.bind(op, lambda x: x)

        mod = Module(
            name="mod",
            steps=(Step("s1", s1), Step("s2", s2)),
            operations=frozenset({op}),
        )
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("already been bound", str(cm.exception))

    def test_unbound_declared_operation_at_boot_end_fails(self) -> None:
        op = Operation("unbound.op", str, str)
        mod = Module(name="mod", steps=(), operations=frozenset({op}))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("was not bound", str(cm.exception))

    def test_duplicate_command_fails(self) -> None:
        def s1(ctx: BootContext) -> None:
            ctx.contribute(Command("run", lambda args: "1"))

        def s2(ctx: BootContext) -> None:
            ctx.contribute(Command("run", lambda args: "2"))

        mod = Module(name="mod", steps=(Step("s1", s1), Step("s2", s2)))
        with self.assertRaises(ValueError) as cm:
            Kernel().boot([mod])
        self.assertIn("Duplicate command name", str(cm.exception))

    # =========================================================================
    # E. Readiness, Lifecycle, and Invoker State
    # =========================================================================

    def test_single_use_kernel(self) -> None:
        kernel = Kernel()
        kernel.boot([])
        with self.assertRaises(RuntimeError) as cm:
            kernel.boot([])
        self.assertIn("Kernel can only boot once", str(cm.exception))

    def test_failed_boot_locks_kernel(self) -> None:
        op = Operation("unbound", str, str)
        mod = Module(name="mod", steps=(), operations=frozenset({op}))
        kernel = Kernel()
        with self.assertRaises(ValueError):
            kernel.boot([mod])

        # Second boot attempt must raise RuntimeError even though first attempt failed
        with self.assertRaises(RuntimeError) as cm:
            kernel.boot([])
        self.assertIn("Kernel can only boot once", str(cm.exception))

    def test_retained_boot_context_disabled_after_successful_boot(self) -> None:
        k = ArtifactKey("k", str)
        op = Operation("op", str, str)
        ctx_ref: list[BootContext] = []

        def s(ctx: BootContext) -> None:
            ctx.provide(k, "val")
            ctx.bind(op, lambda x: x)
            ctx_ref.append(ctx)

        mod = Module(
            name="mod",
            steps=(Step("s", s, provides=frozenset({k})),),
            operations=frozenset({op}),
        )
        Kernel().boot([mod])

        retained = ctx_ref[0]
        with self.assertRaises(RuntimeError):
            retained.require(k)
        with self.assertRaises(RuntimeError):
            retained.provide(k, "new")
        with self.assertRaises(RuntimeError):
            retained.bind(op, lambda x: x)
        with self.assertRaises(RuntimeError):
            retained.contribute(Command("cmd", lambda a: ""))

    def test_retained_boot_context_disabled_after_failed_boot(self) -> None:
        k1 = ArtifactKey("k1", str)
        k2 = ArtifactKey("k2", str)
        ctx_ref: list[BootContext] = []

        def s1(ctx: BootContext) -> None:
            ctx.provide(k1, "v1")
            ctx_ref.append(ctx)

        def s2(ctx: BootContext) -> None:
            ctx_ref.append(ctx)
            raise RuntimeError("Failure inside step s2")

        mod = Module(
            name="mod",
            steps=(
                Step("s1", s1, provides=frozenset({k1})),
                Step("s2", s2, requires=frozenset({k1}), provides=frozenset({k2})),
            ),
        )

        with self.assertRaises(RuntimeError) as cm:
            Kernel().boot([mod])
        self.assertIn("Failure inside step s2", str(cm.exception))

        self.assertEqual(len(ctx_ref), 2)
        for ctx in ctx_ref:
            with self.assertRaises(RuntimeError):
                ctx.require(k1)
            with self.assertRaises(RuntimeError):
                ctx.provide(k2, "val")
            with self.assertRaises(RuntimeError):
                ctx.contribute(Command("cmd", lambda a: ""))

    def test_invoker_disabled_during_boot_and_enabled_after(self) -> None:
        op = Operation("double", int, int)
        invoker_ref: list[Any] = []

        def s1(ctx: BootContext) -> None:
            inv = ctx.require(INVOKER)
            invoker_ref.append(inv)
            # Calling invoker during assembly must fail
            with self.assertRaises(RuntimeError) as cm:
                inv(op, 10)
            self.assertIn("Invoker is disabled", str(cm.exception))
            ctx.bind(op, lambda x: x * 2)

        mod = Module(
            name="mod",
            steps=(Step("s1", s1, requires=frozenset({INVOKER})),),
            operations=frozenset({op}),
        )

        app = Kernel().boot([mod])
        # After successful boot, invoker is enabled
        self.assertEqual(invoker_ref[0](op, 10), 20)
        self.assertEqual(app.invoke(op, 10), 20)

    def test_invoker_disabled_after_failed_boot(self) -> None:
        op = Operation("op", int, int)
        invoker_ref: list[Any] = []

        def s1(ctx: BootContext) -> None:
            inv = ctx.require(INVOKER)
            invoker_ref.append(inv)
            ctx.bind(op, lambda x: x)
            # Step deliberately fails
            raise RuntimeError("Step s1 exploded")

        mod = Module(
            name="mod",
            steps=(Step("s1", s1, requires=frozenset({INVOKER})),),
            operations=frozenset({op}),
        )

        with self.assertRaises(RuntimeError):
            Kernel().boot([mod])

        # Leaked invoker reference must remain unusable
        with self.assertRaises(RuntimeError) as cm:
            invoker_ref[0](op, 42)
        self.assertIn("Invoker is disabled", str(cm.exception))

    def test_invoker_and_app_reject_unknown_operation(self) -> None:
        op_registered = Operation("known.op", str, str)
        op_unknown = Operation("unknown.op", str, str)

        def s(ctx: BootContext) -> None:
            ctx.bind(op_registered, lambda s: s.upper())

        mod = Module(
            name="mod",
            steps=(Step("s", s),),
            operations=frozenset({op_registered}),
        )
        app = Kernel().boot([mod])

        with self.assertRaises(ValueError) as cm:
            app.invoke(op_unknown, "hello")
        self.assertIn("Unknown operation: unknown.op", str(cm.exception))

    def test_app_does_not_expose_artifacts_and_commands_immutable(self) -> None:
        mod = Module(name="mod", steps=())
        app = Kernel().boot([mod])
        self.assertFalse(hasattr(app, "artifacts"))
        self.assertFalse(hasattr(app, "_artifacts"))
        self.assertIsInstance(app.commands, tuple)

    def test_successful_boot_full_flow(self) -> None:
        k_config = ArtifactKey("test.config", str)
        op_greet = Operation("test.greet", str, str)

        def step1_run(ctx: BootContext) -> None:
            ctx.provide(k_config, "Hello")

        def step2_run(ctx: BootContext) -> None:
            prefix = ctx.require(k_config)
            ctx.bind(op_greet, lambda name: f"{prefix}, {name}!")
            ctx.contribute(Command("greet", lambda args: f"{prefix}, {args[0]}!"))

        mod1 = Module(
            name="mod1",
            steps=(Step("step1", step1_run, provides=frozenset({k_config})),),
        )
        mod2 = Module(
            name="mod2",
            steps=(Step("step2", step2_run, requires=frozenset({k_config})),),
            operations=frozenset({op_greet}),
        )

        app = Kernel().boot([mod2, mod1])  # Shuffled input order

        # Verify command contribution
        self.assertEqual(len(app.commands), 1)
        self.assertEqual(app.commands[0].name, "greet")
        self.assertEqual(app.commands[0].run(["World"]), "Hello, World!")

        # Verify operation invocation
        result = app.invoke(op_greet, "Alice")
        self.assertEqual(result, "Hello, Alice!")


if __name__ == "__main__":
    unittest.main()
