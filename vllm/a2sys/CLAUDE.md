# vllm/a2sys/ — our code

This directory is **A**: code with no counterpart upstream. Upstream never creates these
paths, so nothing here conflicts and nothing here needs to track upstream. The rules in
`vllm/CLAUDE.md` govern upstream files and do not apply here.

## The one thing that matters: no disguised copies

If a file here is an upstream file with edits — same class names, same method order, an
upstream-shaped `load_weights`, a docstring naming a model or backend vLLM already ships —
it is **B**, not A, and belongs in `vllm/` edited in place.

The failure is invisible: a copy keeps working while upstream fixes bugs in the original,
and nothing reports the divergence. Merge conflicts are the only mechanism that pulls those
fixes in, and a copy has none.

CI checks this mechanically (`a2sys-gates.yml`, copy detection), so treat a flagged file as
a design question, not a false positive.

The one sanctioned exception is `vllm/a2sys/vendor/`: a pristine `_base/` copy alongside a
pinned `VERSION`, resynced with `git merge-file`. Keep it under four files; past that,
move the code back to `vllm/` and edit in place.

## Rules

- **Subclass instead of reimplementing.** If this re-derives logic an upstream class already
  has, subclassing keeps upstream's improvements flowing in.
- **`register()` must be re-entrant.** `vllm/a2sys/plugin.py` runs in every process — API
  server, engine core, each worker, and the model-inspection subprocess. Guard against
  double registration.
- **Lazy-import anything that initializes CUDA.** Register models by `"module:Class"` string,
  not by importing the class at plugin load, or forked workers fail with
  `Cannot re-initialize CUDA in forked subprocess`.
- **Config goes in `vllm/a2sys/config.py`,** read from `--additional-config`. Never add to
  `vllm/envs.py`; do not scatter bare `os.environ` reads across modules.
- **Two model runners exist.** `vllm/v1/worker/gpu_model_runner.py` and
  `vllm/v1/worker/gpu/model_runner.py` are selected automatically, and code that only works
  under one is *silently ignored* under the other — no error. Never assume a single runner;
  contract tests run under both via `VLLM_USE_V2_MODEL_RUNNER`.
- Python only unless the change is explicitly a kernel. Line length 88. Google-style
  docstrings. Comments and identifiers in English.

## Reviewing

Comment in Korean. Do not flag missing type annotations on internal helpers, test coverage
(CI decides that), or style differences from `vllm/**` — this code is ours and does not need
to merge with anything.
