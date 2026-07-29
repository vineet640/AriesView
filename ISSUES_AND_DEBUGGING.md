# AriesView — Issues Hit While Building, and How They Were Debugged

Real problems encountered while standing up the local RAG stack, written up
for interview prep. Each entry: symptom → how it was diagnosed → root cause
→ fix → the transferable lesson. These make good answers to "tell me about
a bug you debugged" or "what went wrong and how did you handle it."

---

## 1. LLM inference ran at 0.2 tokens/second (the big one)

**Symptom:** The first end-to-end query through the full pipeline failed.
The gateway logged `HeadersTimeoutError` from the LLM call — the model
never even started responding within 5 minutes.

**Diagnosis:** Isolate layers. Retrieval had already succeeded (Weaviate
returned chunks), so the problem was downstream. I bypassed the gateway and
hit Ollama directly with a trivial prompt and timed it: a three-word answer
took 50 seconds, and Ollama's own stats showed **0.2 tokens/second** eval
speed. A healthy Apple-Silicon Mac does 20–30 tok/s on a model this size,
so this wasn't "LLMs are slow" — something was off by two orders of
magnitude.

**Root cause:** Hardware check: Apple M2 with **8GB RAM**. LLaMA 3.1 8B
needs ~5GB resident, and with Docker Desktop's VM, two PyTorch services,
and the OS also in memory, the model was being paged in and out of swap on
every token. The model "ran" — it just thrashed.

**Fix:** Two-part. (1) Default the gateway to `llama3.2:3b` (~2GB), which
fits in memory on this machine, with `OLLAMA_MODEL=llama3.1:8b` as an env
override for machines with 16GB+. Query latency went from timeout to
7–14 seconds. (2) Explicitly unloaded the 8B model from Ollama's memory
(`keep_alive: 0`) to reclaim the RAM immediately.

**Lesson:** When something is 100x too slow, it's rarely the algorithm —
look at the memory hierarchy. Measure at the lowest layer you can isolate
(raw Ollama, not the pipeline) before touching code. This is also exactly
why the production system used a dedicated warm Azure VM sized for the
model: "model fits in memory, always" is an infrastructure requirement,
not an optimization.

---

## 2. HTTP client timeout masked the real problem

**Symptom:** The gateway's error was `TypeError: fetch failed` with cause
`UND_ERR_HEADERS_TIMEOUT` — a generic-looking network error.

**Diagnosis:** Read the actual cause chain in the stack trace instead of
stopping at "fetch failed." Node's built-in `fetch` (undici) has a
**5-minute headers timeout**: if the server doesn't start responding within
5 minutes, the request is aborted. The LLM (see issue #1) was too slow to
produce its first byte in time.

**Root cause:** Two stacked problems — the slow model (real issue) and an
HTTP client whose default timeout was tuned for web requests, not LLM
inference. Even after fixing the model, a cold first generation could
plausibly exceed default timeouts.

**Fix:** Replaced `fetch` with a plain `node:http` request for the
inference call, which has no default headers timeout. Fixed the model
separately.

**Lesson:** Distinguish the *reporter* of an error from its *cause*. The
timeout was the messenger; the swap-thrashing model was the disease. Fix
both, but know which is which — and know your HTTP client's default
timeouts when calling slow backends like LLM inference endpoints.

---

## 3. Port 8080 already allocated — a ghost from a previous deployment

**Symptom:** `docker compose up` failed: "Bind for 0.0.0.0:8080 failed:
port is already allocated."

**Diagnosis:** `docker ps` + `lsof -iTCP:8080` showed *another* Weaviate
container (`ariesview_weaviate`) already running — plus Redis, Prometheus,
and Postgres containers from an older, abandoned version of the same
project. They were configured to auto-start with Docker Desktop.
`docker inspect` on the container revealed which compose project and
directory they came from.

**Root cause:** Stale infrastructure from a previous attempt at the project
resurrecting itself on daemon startup and squatting on the port.

**Fix:** Stopped the old containers (kept their volumes — reversible),
started the new stack, and later fully removed the old containers, volumes,
and project directory once confirmed obsolete. Care point: the old and new
volumes had nearly identical names (`ariesview_rag_weaviate_data` vs
`ariesview_weaviate_data`) — deleting the wrong one would have destroyed
the live index.

**Lesson:** "Port already in use" should trigger *identify the occupant*,
not *change my port*. And when cleaning up look-alike resources, verify
ownership (labels, inspect output) before deleting — near-identical naming
is where data-loss accidents live.

---

## 4. Jest wouldn't run at all on Node 25

**Symptom:** Every test suite failed instantly with
`SecurityError: Cannot initialize local storage without a
--localstorage-file path` — before a single test executed.

**Diagnosis:** The error came from `jest-environment-node` copying Node's
globals, not from any test code. Node 25 added a `localStorage` global that
throws when accessed without a backing file; Jest's environment setup
touches every global, tripping it.

**Root cause:** Ecosystem version skew — a brand-new Node runtime feature
interacting badly with a test framework that predates it.

**Fix:** One line: run Jest with
`NODE_OPTIONS=--localstorage-file=/tmp/... jest` in the test script, which
gives the global a backing file so it initializes cleanly.

**Lesson:** When a tool fails before your code runs, suspect the
environment, not the code. Bleeding-edge runtime versions break tooling in
ways that look scary but are usually one flag away from fixed.

---

## 5. Killing the launcher shell killed the services

**Symptom:** After stopping a background shell that had run the dev-startup
script, health checks showed the embedding service, ingestion service, and
frontend were all down — even though they'd been started with `nohup ... &`.

**Diagnosis:** Re-ran health checks per service to see exactly what died
(the API gateway survived — because it had been started from a *different*
shell). Only the processes launched by the killed shell were gone.

**Root cause:** `nohup` protects against SIGHUP, but the services were
still in the launcher's process group; terminating the tracked shell took
its process tree with it.

**Fix:** Relaunched with `nohup ... & disown` from a short-lived shell so
the servers were fully detached from any tracked process. Verified all
health endpoints afterward.

**Lesson:** Process lifetime is about process groups and parents, not just
`nohup`. If a service must outlive its launcher, actually detach it
(`disown`, `setsid`, or a real supervisor) — and verify by killing the
launcher.

---

## 6. Whole laptop slowed down while the stack was running

**Symptom:** The entire machine — not just the app — became sluggish.

**Diagnosis:** `vm.swapusage` showed **8.1GB of swap in use** on an 8GB
machine with 15% memory free. Top consumers: Ollama's llama-server (2.1GB
resident), Docker Desktop's VM, two PyTorch-loaded Python services, plus a
browser.

**Root cause:** The architecture's deliberate trade-off — keep every model
warm in memory to avoid cold starts — assumes dedicated hardware. On a
shared 8GB laptop, "always loaded" means "everything else swaps."

**Fix/mitigation:** Stop the stack when not in use (`scripts/stop.sh` +
quitting Docker Desktop, since the VM holds memory even with containers
stopped); cap Docker Desktop's memory allocation; rely on Ollama's idle
auto-unload.

**Lesson:** Warm-model serving is a *capacity commitment*, not a free
latency win. This is the same reasoning as the production Azure Functions →
dedicated VM decision, seen from the other side: the VM eliminated cold
starts precisely because it dedicated memory to the models 24/7.

---

## 7. Document list showed internal UUIDs instead of filenames

**Symptom:** `GET /documents` returned
`0ba3d431-..._Lease_Agreement_TenantA.pdf` instead of
`Lease_Agreement_TenantA.pdf`.

**Diagnosis:** Traced where `source_file` was set. Raw uploads are stored
as `{document_id}_{filename}` to prevent collisions; the parser derived
`source_file` from that storage path instead of the original upload
filename, so the internal naming leaked into user-facing metadata.

**Fix:** Set `source_file` from the original filename at ingest time, and
migrated the two already-parsed records.

**Lesson:** Keep storage-layer naming concerns out of user-facing metadata
— capture display fields at the boundary where the true value exists (the
upload), not by parsing them back out of internal identifiers. Small bug,
but the class of bug (derived data reconstructed from the wrong source)
also causes real data-integrity issues at scale.

---

## 8. Azure SDK rejected by Azurite: API version skew

**Symptom:** Wiring the ingestion service to real Azure Blob Storage (via
Azurite, the official local emulator) failed on the very first call —
`create_container` raised `HttpResponseError: The API version 2026-06-06
is not supported by Azurite`.

**Diagnosis:** Read the actual error body instead of assuming a config
mistake. The message named the cause directly: the installed
`azure-storage-blob` SDK defaults to a Storage REST API version newer than
the pinned Azurite Docker image (`3.32.0`) understands. Two independently
versioned things — the SDK and the emulator — had drifted apart.

**Fix:** Azurite ships a documented escape hatch for exactly this
mismatch: `--skipApiVersionCheck` on the container's command line. Added it
to the `azurite` service in `docker-compose.yml`; verified by actually
ingesting a real PDF and confirming both blobs (`raw-documents`,
`parsed-documents`) exist in Azurite via a direct `BlobServiceClient`
listing, not just a 200 response.

**Lesson:** When a cloud SDK talks to a local emulator, the emulator's pinned
version and the SDK's version are two separate moving parts — a working
setup today can break on a `pip install --upgrade` alone. Read the error
body before guessing; official emulators usually document the exact flag
for known compatibility gaps, and verifying "it returned success" is not
the same as verifying "the data is actually there."

---

## 9. CI's Node version didn't match the fix it was supposed to run

**Symptom:** The first GitHub Actions run failed the gateway's Jest suite
immediately: `node: --localstorage-file= is not allowed in NODE_OPTIONS`
— a different error than the one that flag was written to fix (see issue
#4 above).

**Diagnosis:** The CI workflow pinned Node to version 20 (a reasonable-
looking default when writing the workflow). But `--localstorage-file` is
only a valid `NODE_OPTIONS` flag on the Node version whose *new*
`localStorage` global made it necessary in the first place — Node 25,
the version actually used in local development. Node 20 doesn't recognize
the flag via `NODE_OPTIONS` at all, so the exact fix for one Node version
became a hard failure on another.

**Fix:** Set the workflow's `node-version` to `25`, matching local dev
instead of an arbitrary LTS default.

**Lesson:** A version-specific workaround is only portable to the *same*
version. Pinning CI to "whatever LTS looks reasonable" instead of the
version actually used in development is itself a way to reintroduce a bug
you already fixed once — the CI environment should mirror local dev
closely enough that this doesn't happen. This is the same shape of problem
as issue #8 above, just between the test runtime and the app instead of
the app and its cloud emulator.

---

## Quick-reference: one-liners if asked "what problems did you hit?"

1. **8B model on an 8GB machine swap-thrashed to 0.2 tok/s** → measured raw
   inference in isolation, right-sized the model with an env override for
   bigger hardware.
2. **HTTP client's 5-min headers timeout aborted slow LLM calls** → read
   the error's cause chain, swapped to a client without that default.
3. **Stale containers from an old deployment squatted on port 8080** →
   `docker inspect` to identify the owner, stopped/removed them without
   touching the near-identically-named live volume.
4. **Node 25 broke Jest before any test ran** → environment issue, not
   code; fixed with one runtime flag.
5. **`nohup` didn't stop services dying with their launcher shell** →
   process groups matter; properly detached them.
6. **Warm models made the whole laptop swap** → warm serving is a capacity
   commitment; that's *why* production used a dedicated VM.
7. **Internal UUID naming leaked into the API** → capture display metadata
   at the source, don't reconstruct it from storage paths.
8. **Azure SDK vs. Azurite version skew rejected every blob call** → read
   the error body, applied Azurite's documented `--skipApiVersionCheck`
   flag, verified by listing the actual blobs, not just the HTTP status.
9. **CI pinned to Node 20 broke a fix written for Node 25** → matched CI's
   Node version to local dev instead of guessing an LTS default.
