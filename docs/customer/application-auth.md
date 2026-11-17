# Application authentication for the customer POC

Return to the [deployment runbook](azure-devops-markdown-poc.md).
This profile uses **classic UI/orchestrator Container Apps**, not hosted
Foundry Agent Service. A VPN connection does not authenticate a user to the app.

## Customer-owned Entra registration

Have the customer identity administrator:

1. Register a confidential **Web** application in the customer tenant, with
   accounts restricted to that directory.
2. Expose its API scope `api://<client-id>/user_impersonation` and arrange the
   consent required by the customer's policy.
3. Register the exact UI HTTPS redirect URI:
   `<UI-HTTPS-origin>/auth/oauth/azure-ad/callback`.
   Include any supported deployment prefix; use this deployment's origin.
4. Create the approved server-side credential and record its expiry/rotation
   owner. Store the credential value in customer Key Vault, never in the
   profile JSON, source control, browser configuration or deployment logs.
5. Approve allowed users and the identities/roles used by the running services.
   Subscription roles, UI admission and source/document permissions are distinct.

## Required UI runtime configuration

Publish settings through the component's supported App Configuration path with
label `agent-lz`; use Key Vault references for secrets.

| Key | Required meaning |
| --- | --- |
| `OAUTH_AZURE_AD_CLIENT_ID` | Customer application/client ID |
| `OAUTH_AZURE_AD_TENANT_ID` | Customer directory ID |
| `OAUTH_AZURE_AD_ENABLE_SINGLE_TENANT` | `true` |
| `OAUTH_AZURE_AD_CLIENT_SECRET` | Key Vault reference resolving the credential **value**, not its secret ID |
| `OAUTH_AZURE_AD_SCOPES` | `api://<client-id>/user_impersonation` plus `openid`, `profile`, `offline_access` |
| `CHAINLIT_URL` | Canonical external UI HTTPS origin; important behind TLS-terminating ingress |
| `CHAINLIT_AUTH_SECRET` | Persistent protected session-signing secret, not a new random value per instance |
| `ALLOW_ANONYMOUS` | `false` |

The UI identity needs scoped permission to resolve the Key Vault references.
Graph scopes such as `User.Read` are rejected by this callback contract.
Do not assume an arbitrary `azd env set` creates a runtime key: verify it was
published and resolved without exposing its secret value.

The profile also publishes `CHAT_BACKEND=orchestrator` and selects `maf_lite`.
Preserve the deployed classic inter-service authentication and approved
orchestrator binding. Hosted-specific Foundry OBO settings are not substitutes.

## Admission

`ALLOWED_USER_PRINCIPALS` accepts comma-separated `tenant-id:object-id` values.
`ALLOWED_USER_NAMES` is an alternative list of sign-in names. They combine with
**OR**; empty lists admit all successfully authenticated users. Configure them
deliberately for the approved POC audience.

The callback does not fetch Graph group membership. These lists restrict UI
admission, not per-document retrieval. The UI caches configuration at startup;
after approved changes reload/redeploy the process and start a fresh sign-in.
Provisioning can republish template-owned settings.

## Acceptance and failure boundaries

- A signed-out caller cannot chat.
- An approved user signs in through the exact callback, reaches the UI and can
  query the intended orchestrator.
- A user absent from both **nonempty** admission lists is denied.
- Session-signing state remains compatible across intended restarts/instances.
- A different user cannot open another user's conversation history.
- Tokens, credentials and document contents are not printed as test evidence.

Redirect mismatch concerns the exact origin/callback. Consent/refresh errors
concern tenant, scopes, credential lifetime and consent. Private endpoint
failures concern [network/DNS access](private-access.md); service-role failures
concern the actual caller identity and approved scope.
Do not enable anonymous access, replace a delegated caller with fabricated
headers or weaken data access as a recovery measure.

Azure DevOps repository permissions are not automatically propagated into
Search. Until an approved document-permission contract and independent-user
allow/deny tests pass, this profile is restricted to synthetic or explicitly
admitted common-audience non-sensitive content.
