---
name: troubleshoot-lab-setup
description: Verify the Gemini World lab environment is set up correctly, and diagnose/fix common errors. Use at the START of the lab right after logging in to confirm everything is ready ("check my setup", "am I ready to start", "verify my environment", "did I log in correctly"), AND whenever the user hits an error and doesn't know why — permission denied / 403 / PERMISSION_DENIED, "API not enabled", a deploy that fails, the frontend can't reach the agent, /chat errors, code sandbox failures, image generation failures, or a vague "it's not working". Checks the usual culprits: signed into Antigravity with the right account (GCP/lab flow, not personal Google login), the GCP project is set, both gcloud auth login and application-default login have run, the API is enabled, and the identity has roles/aiplatform.user. Don't use for writing agent features or non-error build questions.
---

# Troubleshoot the lab setup

Nearly every failure in this lab is one of a handful of environment problems —
not the user's code. This skill has **two modes**:

- **Preflight** — run at the *start* of the lab, right after the user logs in, to
  confirm everything is ready before they build. Catches problems early instead
  of mid-module.
- **Error triage** — run when the user hits an error. Run the checks below first,
  fix what's wrong, then jump to the matching symptom.

Prefer *verifying* state with a read command before *changing* anything, and tell
the user what you found.

## Preflight: start-of-lab health check

When the user asks to verify their setup (or you're kicking off the lab), run
**checks 0-4 below in order** and report a clear pass/fail summary, e.g.:

```
Setup check:
✅ Antigravity signed in as <lab account>
✅ Project set to <qwiklabs project id>
✅ gcloud auth + ADC present
✅ Vertex AI / aiplatform API enabled
✅ roles/aiplatform.user granted
You're ready to start. ✅
```

Fix anything that fails, then re-run that check before moving on. Skip the
deploy/frontend/sandbox symptoms during preflight — those come up later.

## The checks (run these for almost ANY error, and for preflight)

These are the usual culprits. Check all of them before deep-diving.

**0. Is the user signed into Antigravity with the RIGHT account?** A very common
trap: signing into Antigravity with a personal **Google login** (e.g. a
`@gmail.com` or `@google.com` account) instead of the **GCP / Qwiklabs lab
credentials**. Everything *looks* fine, but calls to the project fail with
permission errors because AGY is acting as the wrong identity.

- Ask the user which account they used to sign into Antigravity, and confirm it's
  the **Qwiklabs lab account**, not their personal Google account.
- Cross-check the active gcloud account matches the lab account:
  ```bash
  gcloud auth list        # the ACTIVE (*) account should be the lab account
  ```
- If AGY is signed in with the wrong account, have the user sign out of
  Antigravity and sign back in using the GCP/lab login flow (per the lab's setup
  instructions), then re-run the preflight.

**1. Is the right project set?** Cloud Shell / AGY can silently default to the

**1. Is the right project set?** Cloud Shell / AGY can silently default to the
wrong project (e.g. `cloudshell-gca`), which makes enable/deploy commands fail.

```bash
gcloud config get-value project          # what's active right now?
echo "$GOOGLE_CLOUD_PROJECT"             # what the env thinks it is
```

If either is wrong or empty, pin it to the Qwiklabs Project ID:

```bash
export GOOGLE_CLOUD_PROJECT=<your qwiklabs project id>
gcloud config set project "$GOOGLE_CLOUD_PROJECT"
```

Also confirm the project is pinned inside AGY's own settings so it can't switch
mid-run.

**2. Has the user authenticated?** Two separate logins are required — a missing
Application Default Credentials (ADC) login is the #1 cause of 403s from code.

```bash
gcloud auth list                          # is there an active account?
```

If not authenticated, run BOTH:

```bash
gcloud auth login
gcloud auth application-default login
```

**3. Is the needed API enabled?** Deploy, sandbox, and model calls need the
Agent Platform / Vertex AI API on. "API not enabled" errors usually mean this or
the wrong project (see #1).

```bash
gcloud services list --enabled | grep -i aiplatform
gcloud services enable aiplatform.googleapis.com   # enable if missing
```

**4. Does the identity have the right IAM role?** Many features need
`roles/aiplatform.user`. If a call is `PERMISSION_DENIED`, check the role on
whichever identity is making the call (your user, the agent's service account, or
the Cloud Run service account).

```bash
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
  --member="user:<you@example.com>" \
  --role="roles/aiplatform.user"
```

> Tip: if you have the **Developer Knowledge MCP** installed, use it to confirm
> the exact API name, role, and command for a given product instead of guessing.

## Symptom → fix

### 403 / PERMISSION_DENIED / "permission denied"
Almost always one of: signed into Antigravity with the wrong (personal) account
instead of the lab account (check #0), ADC missing (check #2), a missing
`roles/aiplatform.user` on the calling identity (check #4), or the wrong project
(check #1). Rule those out in that order.

### "API not enabled" / "SERVICE_DISABLED"
You're either on the wrong project (#1) or the API is off (#3). Fix the project
first, then enable.

### `agents-cli deploy` fails
1. Project pinned? (#1) — this is the most common cause.
2. APIs enabled and authenticated? (#2, #3)
3. Re-read the actual error; if it names a permission, go to #4.
List existing deployments to see current state: `agents-cli deploy --list`.

### Frontend can't reach the agent / no reply / errors on send
Run all frontend commands from the `frontend/` folder.
1. Dependencies installed? `pip install -r requirements.txt`
2. Is `AGENT_ENGINE_RESOURCE_NAME` set and correct? It must be the resource name
   from `deployment_metadata.json` (written by the deploy step):
   ```bash
   echo "$AGENT_ENGINE_RESOURCE_NAME"
   export AGENT_ENGINE_RESOURCE_NAME="<paste from deployment_metadata.json>"
   ```
3. ADC present locally? (#2)
4. Sanity test: send a message, then ask "What did I just ask?" — if it can't
   remember, the wiring to the deployed agent is wrong, not the UI.

### `/chat` errors after deploying the frontend to Cloud Run
The Cloud Run service runs as a **different identity** than your local user, so
its service account needs `roles/aiplatform.user`. Grant it to the Cloud Run
service account (not your user account), then retry.

### Code sandbox / code execution fails
1. Agent Platform API enabled (#3) and identity has `roles/aiplatform.user` (#4).
2. Does a sandbox actually exist? If not, create one from the agent engine
   resource before running code.

### Image generation fails
Usually an API/permission issue (#3, #4) or a region/model-access mismatch.
Confirm the model and region are available for the project, and that the API is
enabled.

### Antigravity / MCP behaving oddly right after install
If you just installed agents-cli or the Developer Knowledge MCP, **restart
Antigravity** so it picks up the new skills/MCP, then retry.

## Rules of thumb
- Confirm the **Antigravity account** first — signing in with a personal Google
  account instead of the lab/GCP flow silently breaks project access.
- Fix the **project** next — a wrong project makes half the other errors appear.
- There are **two** auth logins (`login` and `application-default login`); missing
  the second one breaks code-level calls while the CLI still looks fine.
- Match the IAM role to the **identity that actually makes the call** — your user
  locally, but the service account in Cloud Run.
- When unsure of an exact command/role/API name, check the Developer Knowledge MCP
  rather than guessing.
