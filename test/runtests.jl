# Test entry point (ENGINEERING_STANDARDS §2). ReTestItems discovers every `@testitem` under
# `test/` (including `test/testitems/`) and runs them hermetically, in parallel, in CI.
# Each gate is self-contained (its own `using`) so agent-generated tests cannot leak global state.
using ReTestItems, LPJmLFITEmulator

runtests(LPJmLFITEmulator)
