import express from "express"

import { LimiqClient } from "@limiq/sdk-js"

const app = express()
app.use(express.json())

const port = Number(process.env.PORT || 3002)
const kyaBaseUrl = process.env.KYA_BASE_URL || "http://localhost:8000"

function requireField(body, field) {
  if (!body || typeof body !== "object" || !(field in body)) {
    return `Missing required field: ${field}`
  }
  return null
}

app.get("/health", (_, res) => {
  res.json({ ok: true, service: "purchase-target", kya_base_url: kyaBaseUrl })
})

app.post("/purchase", async (req, res) => {
  const body = req.body
  const required = [
    "workspace_id",
    "agent_id",
    "action_type",
    "target_service",
    "payload",
    "signature",
    "capability_token",
  ]

  for (const field of required) {
    const error = requireField(body, field)
    if (error) {
      return res.status(400).json({ ok: false, error })
    }
  }

  try {
    const client = new LimiqClient({
      baseUrl: kyaBaseUrl,
      workspaceId: body.workspace_id,
    })

    const verify = await client.verifyAction({
      workspace_id: body.workspace_id,
      agent_id: body.agent_id,
      action_type: body.action_type,
      target_service: body.target_service,
      payload: body.payload,
      signature: body.signature,
      capability_token: body.capability_token,
      request_context: body.request_context || {},
    })

    if (verify.decision !== "ALLOW") {
      return res.status(403).json({
        ok: false,
        blocked: true,
        reason_code: verify.reason_code,
        audit_event_id: verify.audit_event_id,
      })
    }

    return res.json({
      ok: true,
      executed: true,
      audit_event_id: verify.audit_event_id,
      purchase: {
        amount: body.payload.amount,
        currency: body.payload.currency,
        merchant: body.payload.merchant,
      },
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown verify error"
    return res.status(502).json({ ok: false, error: message })
  }
})

app.listen(port, () => {
  console.log(`purchase-target listening on http://localhost:${port}`)
})
