import { buildSignedRequest, generateKeys } from "@limiq/sdk-js"

const KYA_BASE_URL = process.env.KYA_BASE_URL || "http://localhost:8000"
const TARGET_BASE_URL = process.env.TARGET_BASE_URL || "http://localhost:3002"
const BOOTSTRAP_TOKEN = process.env.KYA_BOOTSTRAP_TOKEN || ""
const DEMO_POLICY_MAX_SPEND = Number(process.env.DEMO_POLICY_MAX_SPEND || "100")
const ALLOW_AMOUNT = Number(process.env.DEMO_ALLOW_AMOUNT || "49")
const DENY_AMOUNT = Number(process.env.DEMO_DENY_AMOUNT || "149")
const DEMO_MODE = (process.env.DEMO_MODE || "both").toLowerCase()

const ACTION_TYPE = "purchase.execute"
const TARGET_SERVICE = "purchase-target"

function randomSuffix() {
  return Math.random().toString(36).slice(2, 10)
}

async function parseResponseJson(resp) {
  const text = await resp.text()
  if (!text) {
    return null
  }
  try {
    return JSON.parse(text)
  } catch {
    return { raw: text }
  }
}

async function postKya(path, body, headers = {}) {
  const resp = await fetch(`${KYA_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...headers,
    },
    body: JSON.stringify(body),
  })

  const data = await parseResponseJson(resp)
  if (!resp.ok) {
    throw new Error(`${path} failed with ${resp.status}: ${JSON.stringify(data)}`)
  }
  return data
}

async function postTargetPurchase(body) {
  const resp = await fetch(`${TARGET_BASE_URL}/purchase`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(body),
  })

  const data = await parseResponseJson(resp)
  return { status: resp.status, data }
}

function printStep(text) {
  console.log(`- ${text}`)
}

function printSuccess(text) {
  console.log(`✅ ${text}`)
}

function printFailure(text) {
  console.error(`❌ ${text}`)
}

async function run() {
  if (!BOOTSTRAP_TOKEN) {
    throw new Error("Missing KYA_BOOTSTRAP_TOKEN env var (required for POST /workspaces)")
  }

  printStep(`Limiq.io API: ${KYA_BASE_URL}`)
  printStep(`Target API: ${TARGET_BASE_URL}`)

  const workspace = await postKya(
    "/workspaces",
    {
      name: `Purchase Demo ${randomSuffix()}`,
      slug: `purchase-demo-${randomSuffix()}`,
    },
    {
      "X-Bootstrap-Token": BOOTSTRAP_TOKEN,
    },
  )
  const workspaceId = workspace.id
  printSuccess(`workspace created: ${workspaceId}`)

  const keys = generateKeys()

  const agent = await postKya(
    "/agents",
    {
      workspace_id: workspaceId,
      name: `purchase-agent-${randomSuffix()}`,
      public_key: keys.publicKeyBase64,
      runtime_type: "demo",
      metadata: {
        integration: "purchase-target",
      },
    },
    {
      "X-Workspace-Id": workspaceId,
      "X-Actor-Id": "purchase-demo",
    },
  )
  printSuccess(`agent created: ${agent.id}`)

  const policy = await postKya(
    "/policies",
    {
      workspace_id: workspaceId,
      name: "purchase-policy",
      version: 1,
      schema_version: 1,
      policy_json: {
        allowed_tools: [ACTION_TYPE],
        spend: { max_per_tx: DEMO_POLICY_MAX_SPEND },
      },
    },
    {
      "X-Workspace-Id": workspaceId,
      "X-Actor-Id": "purchase-demo",
    },
  )
  printSuccess(`policy created: ${policy.id}`)

  const binding = await postKya(
    `/agents/${agent.id}/bind_policy`,
    {
      workspace_id: workspaceId,
      policy_id: policy.id,
    },
    {
      "X-Workspace-Id": workspaceId,
      "X-Actor-Id": "purchase-demo",
    },
  )
  printSuccess(`policy bound: ${binding.id}`)

  const capability = await postKya(
    "/capabilities/request",
    {
      workspace_id: workspaceId,
      agent_id: agent.id,
      action: ACTION_TYPE,
      target_service: TARGET_SERVICE,
      requested_scopes: [ACTION_TYPE],
      requested_limits: { amount: DEMO_POLICY_MAX_SPEND },
      ttl_minutes: 15,
    },
    {
      "X-Workspace-Id": workspaceId,
      "X-Actor-Id": "purchase-demo",
    },
  )
  printSuccess("capability issued")

  if (DEMO_MODE === "allow" || DEMO_MODE === "both") {
    const allowPayload = {
      amount: ALLOW_AMOUNT,
      currency: "USD",
      merchant: "Demo Store",
      order_ref: `allow-${randomSuffix()}`,
    }

    const allowRequest = buildSignedRequest({
      workspace_id: workspaceId,
      agent_id: agent.id,
      action_type: ACTION_TYPE,
      target_service: TARGET_SERVICE,
      payload: allowPayload,
      capability_token: capability.token,
      privateKeyBase64: keys.privateKeyBase64,
      request_context: { source: "agent-demo", scenario: "ALLOW" },
    })

    const allowResp = await postTargetPurchase(allowRequest)
    if (allowResp.status !== 200 || allowResp.data?.executed !== true) {
      throw new Error(`ALLOW scenario failed: status=${allowResp.status} body=${JSON.stringify(allowResp.data)}`)
    }

    printSuccess("verify = ALLOW")
    printSuccess("action executed")
  }

  if (DEMO_MODE === "deny" || DEMO_MODE === "both") {
    const denyPayload = {
      amount: DENY_AMOUNT,
      currency: "USD",
      merchant: "Demo Store",
      order_ref: `deny-${randomSuffix()}`,
    }

    const denyRequest = buildSignedRequest({
      workspace_id: workspaceId,
      agent_id: agent.id,
      action_type: ACTION_TYPE,
      target_service: TARGET_SERVICE,
      payload: denyPayload,
      capability_token: capability.token,
      privateKeyBase64: keys.privateKeyBase64,
      request_context: { source: "agent-demo", scenario: "DENY" },
    })

    const denyResp = await postTargetPurchase(denyRequest)
    if (denyResp.status !== 403) {
      throw new Error(`DENY scenario failed: expected 403, got ${denyResp.status} body=${JSON.stringify(denyResp.data)}`)
    }

    const reasonCode = denyResp.data?.reason_code
    if (reasonCode !== "SPEND_LIMIT_EXCEEDED") {
      throw new Error(
        `DENY scenario failed: expected reason_code=SPEND_LIMIT_EXCEEDED, got ${JSON.stringify(reasonCode)} body=${JSON.stringify(denyResp.data)}`,
      )
    }

    printSuccess("verify = DENY (reason=SPEND_LIMIT_EXCEEDED)")
  }

  printSuccess("Integration proof completed")
}

run().catch((error) => {
  const message = error instanceof Error ? error.message : String(error)
  printFailure(message)
  process.exit(1)
})
