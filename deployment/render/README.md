# Free-only hosted candidate

The selected backend is one Render **Free** Python web service. It serves the
existing API and Atlas; the immutable FDA archive remains on Hugging Face.
Python 3.15.1 and uv 0.13.6 are explicit, and application dependency locks are
unchanged. No new framework, database service, disk, hardware upgrade or paid
Space is required.

The root `render.yaml` is the reviewed Blueprint. Build/start scripts reuse the
existing locked server extra and ASGI factory. Render generates the private
cursor-integrity key inside its environment; no HF/GitHub credential is copied.
`RENDER_GIT_COMMIT` binds the native application identity. A new ephemeral cache
is built from the exact previously permitted public archive after each start.

## Zero-cost activation boundary

Before applying the Blueprint, verify the authenticated owner/workspace and
confirm it has **no payment method**. Keep the service plan `free`, automatic
redeployments off, and all paid resources absent. Do not add a payment method,
buy credits, upgrade a plan or change another workspace's billing. Render can
bill bandwidth/build overages when a payment method exists; without one,
exhausted allowances suspend the service/builds. Free services also sleep after
15 idle minutes. This is a bounded candidate, not an availability guarantee.

An authenticated Render session is required for activation. No Render account
or credential is currently recorded in this repository. Account sign-in and
any new provider consent remain human. Prepare the Blueprint and protected PR
before that final native step; do not claim that a configuration file is a live
service.

After activation, record the native service ID, free plan, actual assigned URL,
source commit and successful health/readiness. Dispatch `hf-space-service.yml`
from main with `exact_commit` and `endpoint` to run read-only HTTP/provenance and
Chromium checks on GitHub Actions. Endpoint validation accepts only the GMA
Render hostname (including its generated suffix) or the local CI container.
No provider token is required for those public checks.

The old Docker Space deployment is retired and fails closed before loading a
credential or contacting Hugging Face. The old native HTTP 402 receipt remains
historical evidence. #61 stays open while the actual endpoint or required
production temporal evidence remains unqualified.

References: https://render.com/docs/free and
https://render.com/docs/python-version.
