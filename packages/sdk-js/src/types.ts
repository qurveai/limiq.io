export type VerifyEnvelopeInput = {
  agent_id: string
  workspace_id: string
  action_type: string
  target_service: string
  payload: Record<string, unknown>
  capability_jti: string
}

export type GenerateKeysResult = {
  publicKeyBase64: string
  privateKeyBase64: string
}

export type SignActionInput = VerifyEnvelopeInput & {
  privateKeyBase64: string
}

export type SignActionResult = {
  signatureBase64: string
  canonicalJson: string
  sha256Hex: string
}

export type BuildSignedRequestInput = {
  workspace_id: string
  agent_id: string
  action_type: string
  target_service: string
  payload: Record<string, unknown>
  capability_token: string
  privateKeyBase64: string
  request_context?: Record<string, unknown>
}

export type VerifyRequestBody = {
  workspace_id: string
  agent_id: string
  action_type: string
  target_service: string
  payload: Record<string, unknown>
  signature: string
  capability_token: string
  request_context: Record<string, unknown>
}

export type VerifyResponse = {
  decision: "ALLOW" | "DENY"
  reason_code: string | null
  audit_event_id: string
}

export type RequestCapabilityInput = {
  agent_id: string
  action: string
  target_service: string
  requested_scopes: string[]
  requested_limits: Record<string, unknown>
  ttl_minutes: number
}

export type RequestCapabilityResponse = {
  token: string
  jti: string
  issued_at: string
  expires_at: string
}

export type LimiqClientOptions = {
  baseUrl: string
  workspaceId: string
  fetchImpl?: typeof fetch
}
