# vllm/ — upstream code

Everything under this directory except `vllm/a2sys/` is **upstream code**. `upstream/main`
is merged into `develop` daily, so every line we change here has a permanent cost: it can
conflict, and it can silently drift.

> Files under `vllm/a2sys/` are ours. This file does not apply to them —
> see `vllm/a2sys/CLAUDE.md`.

A change to an upstream file is **B** (edited in place) or **C** (a hook of 5 lines or
fewer that calls into `vllm/a2sys/`). Before writing either, work down this list.

## 1. Could a registration API have handled this?

If any row matches, the code belongs in `vllm/a2sys/` and should register itself instead.

| If the change is about | Use instead |
|---|---|
| Adding a model architecture | `ModelRegistry.register_model` |
| Replacing or adding an attention backend | `register_backend` — it can **override in-tree backends**, not just add new ones |
| Replacing a layer implementation | `CustomOp.register_oot` |
| A quantization format | `register_quantization_config` |
| KV offload or transfer | `KVConnectorFactory.register_connector` |
| A torch.compile fusion pass | `inductor_passes` |
| Scheduling policy | `scheduler_cls` |
| Worker behaviour | `worker_cls` / `worker_extension_cls` |
| Post-sampling logits work | `logits_processors` |
| Metrics | the `vllm.stat_logger_plugins` entry point |
| A new HTTP route | the `vllm.endpoint_plugins` entry point |
| Any new configuration knob | `--additional-config`, parsed in `vllm/a2sys/config.py` |

`register_backend` overriding in-tree backends is the row people miss most often. Editing
`vllm/v1/attention/backends/**` is almost never necessary.

## 2. Would subclassing do?

Subclassing an upstream class from `vllm/a2sys/` keeps upstream's changes to every part you
did not override flowing in for free. The overridden part still breaks *silently* on
upstream changes, so it needs a contract test asserting our code actually ran.

## 3. If it is C, hold it to the shape

- The hunk is 5 lines or fewer.
- The body lives in `vllm/a2sys/`. A seam calls out; it does not implement.
- The commit carries `Upstream-status:` and `Removable-when:` trailers.
- An upstream issue exists asking for the hook. A seam is meant to disappear.

## 4. If it is genuinely B

In-place editing is then correct. Only these still matter:

- It is edited **in place**, never copied to a new path. A copy stops receiving upstream
  fixes and nothing ever reports the divergence — 39% of commits to
  `vllm/model_executor/models/` over 180 days were fixes.
- It does not drift from upstream style. This code has to keep merging cleanly.
- Nothing here imports `vllm.a2sys` unless the file is a registered seam.

## Off limits

- `csrc/`, `cmake/`, `rust/`, `.buildkite/`, `setup.py` — new CUDA kernels go in
  `vllm/a2sys/ops/` as a separate torch extension.
- `vllm/envs.py` and `vllm/engine/arg_utils.py` — our knobs go under `--additional-config`.

## Reviewing

Comment in Korean. Do not flag style, formatting, or naming inside upstream files: that code
matches upstream on purpose, and deviating from it creates conflicts.
