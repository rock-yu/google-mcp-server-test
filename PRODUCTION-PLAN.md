# Production plan — Google Drive MCP

Plan to move from the **local stdio experiment** in this repo to a **hosted, team-ready MCP service** that clients (Cursor, VS Code Copilot, etc.) reach over HTTPS.

**Baseline (today):** `@modelcontextprotocol/server-gdrive` spawned by the IDE, `stdio` transport, Desktop OAuth client, single-user token file on disk. See [README.md](./README.md) and [SETUP-GUIDE.md](./SETUP-GUIDE.md).

**Target state:** Always-on MCP endpoint, per-user Google consent, secrets in a managed store, authenticated MCP access, observability, and org-approved Google OAuth.

---

## Success criteria (program level)

| Criterion | Measure |
|-----------|---------|
| **Availability** | MCP endpoint reachable over HTTPS with defined SLO (e.g. 99.5% monthly) |
| **Multi-user** | Each user connects their own Drive via OAuth; no shared token file on disk |
| **Security** | TLS, MCP gateway auth, secrets in vault, read-only Drive scope unless explicitly expanded |
| **Compliance** | Data flow documented; logging without storing full file contents by default |
| **Operability** | Health checks, metrics, runbooks, secret rotation documented |

---

## Architecture decision (Milestone 0)

**Complete before build work.** Record the decision in this repo or an ADR.

| Option | Best for | Implications |
|--------|----------|--------------|
| **A — Per-user OAuth** (recommended default) | Each person’s “my Drive” in AI tools | Web OAuth client, token DB/vault per user, user completes consent once |
| **B — Service account + domain-wide delegation** | Google Workspace, centralized read of many Drives | Workspace admin setup; no per-user browser login; not for personal Gmail |

**Transport:** Stock `server-gdrive` is **stdio-only**. Production requires either:

1. **HTTP-native MCP service** — reimplement or wrap tools using `@modelcontextprotocol/sdk` + Streamable HTTP / SSE, or  
2. **stdio bridge** — proxy that spawns the existing binary (faster pilot, weaker at scale).

**Exit criteria:** Signed-off access model (A or B), target cloud (e.g. GCP Cloud Run vs AWS ECS), and transport approach (native HTTP vs bridge).

---

## Phases and milestones

### Phase 1 — Foundation and design  
**Goal:** Agree how we productionize; no production traffic yet.

| ID | Milestone | Key steps | Deliverables | Exit criteria |
|----|-----------|-----------|--------------|---------------|
| **M1.1** | Requirements & scope | Stakeholder use cases; which clients (Cursor, VS Code); read-only vs write; max users; data residency | Short requirements doc | Scope signed off |
| **M1.2** | Architecture decision | Choose OAuth model (A/B), hosting platform, MCP HTTP approach | ADR or section in this plan updated | M0 decisions recorded |
| **M1.3** | Threat model & data flow | Map: user → IDE → MCP → Google; PII/sensitive files; retention | Security one-pager | Security review scheduled or complete |
| **M1.4** | Google Cloud prep | Dedicated GCP project (or folder); Drive API enabled; naming, billing, IAM owners | GCP project ready | Project + owners assigned |

**Phase 1 complete when:** M1.1–M1.4 exit criteria met.

---

### Phase 2 — Identity and Google OAuth (production)  
**Goal:** Replace Desktop OAuth + local JSON with production-grade auth.

| ID | Milestone | Key steps | Deliverables | Exit criteria |
|----|-----------|-----------|--------------|---------------|
| **M2.1** | OAuth client (Web) | Create **Web application** client; HTTPS redirect URIs for staging/prod | Client ID/secret in vault | No Desktop client in prod |
| **M2.2** | Consent screen | Internal (Workspace) or External + verification path; `drive.readonly` scope | Published or Internal app | Test users not required for prod users |
| **M2.3** | Auth service | Login URL → callback → code exchange → store refresh token keyed by `user_id` | Auth API + callback routes | 2+ test users can complete flow in staging |
| **M2.4** | Token store | Encrypt at rest; per-user rows; refresh before expiry | DB or Secret Manager design | Tokens not on container filesystem |

**Phase 2 complete when:** A staging user can sign in with Google and their token is stored and refreshed without using `.gdrive-server-credentials.json`.

---

### Phase 3 — MCP service (build)  
**Goal:** Runnable MCP server that speaks HTTP and uses stored tokens.

| ID | Milestone | Key steps | Deliverables | Exit criteria |
|----|-----------|-----------|--------------|---------------|
| **M3.1** | Service skeleton | Node service: health, config, structured logging | Repo or new service module | `/health` returns 200 locally |
| **M3.2** | MCP HTTP transport | Implement search + resources (parity with local server) via MCP SDK | Tools: `search`; resources: `gdrive:///` | `tools/list` and sample `tools/call` pass integration tests |
| **M3.3** | Drive integration | Inject user token from store; handle quota/rate errors | Drive client module | Read sheet/doc in staging with test user |
| **M3.4** | MCP gateway auth | API key, JWT, or OIDC in front of MCP routes | Auth middleware | Unauthenticated requests rejected |
| **M3.5** | Container image | Dockerfile; non-root user; secrets via env/vault | Image in registry | Image scanned; no secrets baked in |

**Phase 3 complete when:** Staging URL serves MCP over HTTPS; authenticated call reads a known Drive file for a test user.

---

### Phase 4 — Deploy and platform  
**Goal:** Hosted environment ready for pilot users.

| ID | Milestone | Key steps | Deliverables | Exit criteria |
|----|-----------|-----------|--------------|---------------|
| **M4.1** | Staging environment | Deploy to Cloud Run / ECS / K8s; TLS cert; custom domain | Staging URL | HTTPS MCP endpoint live |
| **M4.2** | Secrets & config | OAuth client secret, DB credentials, signing keys in vault | IaC or runbook | No prod secrets in git |
| **M4.3** | Networking | Egress to `googleapis.com`; corporate proxy documented if needed | Network diagram | Drive API calls succeed from cluster |
| **M4.4** | CI/CD | Build, test, deploy pipeline; promote staging → prod | Pipeline | One-click deploy to staging |
| **M4.5** | Production environment | Prod URL; separate OAuth redirect; stricter IAM | Prod URL | Prod mirrors staging config |

**Phase 4 complete when:** Prod endpoint exists but access limited to pilot group.

---

### Phase 5 — Operate, observe, comply  
**Goal:** Safe to widen usage beyond pilot.

| ID | Milestone | Key steps | Deliverables | Exit criteria |
|----|-----------|-----------|--------------|---------------|
| **M5.1** | Observability | Metrics (latency, errors, Google 429/403); alerting | Dashboards + alerts | On-call can detect outage |
| **M5.2** | Audit logging | Log tool name, user id, file id — not full file body by default | Log schema | Sample audit trail reviewed |
| **M5.3** | Runbooks | Token revoke, re-consent, secret rotation, Google quota | Runbook doc | DR exercise or tabletop done |
| **M5.4** | Rate limits & quotas | Per-user limits; backoff on Google API errors | Config | Load test within agreed bounds |
| **M5.5** | Compliance sign-off | Privacy / security approval for team rollout | Sign-off record | Go for general availability |

**Phase 5 complete when:** M5.1–M5.5 met; GA approval granted.

---

### Phase 6 — Client rollout and GA  
**Goal:** Team uses hosted MCP instead of local stdio.

| ID | Milestone | Key steps | Deliverables | Exit criteria |
|----|-----------|-----------|--------------|---------------|
| **M6.1** | Client config template | Document `mcp.json` / Cursor config pointing to prod URL + auth headers | Client config doc (README section or separate guide) | 3 pilot users connected |
| **M6.2** | User onboarding | “Connect Google Drive” flow; support FAQ | Internal wiki page | Pilot feedback incorporated |
| **M6.3** | Deprecate local path | Communicate local-only setup as dev-only; optional feature flag | Comms | New users default to hosted |
| **M6.4** | General availability | Open to target user population | Launch note | Adoption metric tracked |

**Phase 6 complete when:** Hosted MCP is the supported path for the target audience.

---

## Timeline (indicative)

Assumes part-time platform + one engineer. Adjust for team size.

| Phase | Duration (guide) | Cumulative |
|-------|------------------|------------|
| Phase 1 — Foundation | 1–2 weeks | Week 2 |
| Phase 2 — OAuth | 2–3 weeks | Week 5 |
| Phase 3 — MCP build | 3–4 weeks | Week 9 |
| Phase 4 — Deploy | 1–2 weeks | Week 11 |
| Phase 5 — Operate | 2 weeks (parallel with late Phase 4) | Week 11 |
| Phase 6 — Rollout | 1–2 weeks | Week 13 |

**First pilot (M6.1):** ~week 10–11 if Phase 3 staging is stable.  
**GA (M6.4):** ~week 12–13 with security/compliance sign-off.

---

## Workstreams (who does what)

| Workstream | Owner (typical) | Phases |
|------------|-----------------|--------|
| Product / use cases | Architect or product | 1, 6 |
| Security & compliance | Security | 1, 5 |
| Google Cloud / OAuth | Platform or backend | 2, 4 |
| MCP service development | Backend | 3, 4 |
| Infrastructure & CI/CD | Platform | 4, 5 |
| Client documentation | Developer experience | 6 |

---

## Risks and mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Google OAuth verification delay (External app) | Blocks non-test users | Start verification early in Phase 2; use Internal if Workspace-only |
| `server-gdrive` stdio-only | Rework if bridge insufficient | Commit to HTTP-native in M0; spike in Week 1 |
| Single token file anti-pattern in prod | Data leak, wrong user’s Drive | Per-user vault from M2.4; block prod deploy without it |
| Drive API quotas | Throttling at scale | Per-user rate limits; monitor 429; request quota increase |
| Corporate TLS proxy | Auth/API failures | Proper CA trust in container; do not use `NODE_TLS_REJECT_UNAUTHORIZED=0` in prod |
| MCP client transport differences | Cursor vs VS Code config drift | Test both clients in M6.1 |

---

## Local experiment vs production (reference)

| Aspect | Local ([SETUP-GUIDE.md](./SETUP-GUIDE.md)) | Production |
|--------|---------------------------------------------|------------|
| Transport | `stdio` | HTTPS + MCP Streamable HTTP / SSE |
| OAuth client | Desktop | Web |
| Credentials | `gcp-oauth.keys.json` + `.gdrive-server-credentials.json` on disk | Vault + per-user tokens |
| Process | IDE-spawned | Container / serverless |
| Auth to MCP | Implicit (local machine) | API key / OIDC |

---

## Next actions (immediate)

1. **Schedule M0 workshop** — decide per-user OAuth vs service account; pick cloud and HTTP approach.  
2. **Open GCP production project** (M1.4) if not already separate from the experiment project.  
3. **Spike MCP HTTP** (3–5 days) — prove `tools/list` + one Drive read against staging auth.  
4. **Link this plan** from README for discoverability.

---

## Related documents

- [README.md](./README.md) — local setup and credentials  
- [SETUP-GUIDE.md](./SETUP-GUIDE.md) — developer onboarding (local)  
- [research/mcp-connector-research-dossier.md](./research/mcp-connector-research-dossier.md) — MCP layers, transport, connector model  
