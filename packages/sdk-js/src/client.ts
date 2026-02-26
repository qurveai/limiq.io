import { extractCapabilityJti, signAction } from "./crypto.js"
import type {
  BuildSignedRequestInput,
  LimiqClientOptions,
  RequestCapabilityInput,
  RequestCapabilityResponse,
  VerifyRequestBody,
  VerifyResponse,
} from "./types.js"

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.replace(/\/$/, "")
}

function buildHeaders(workspaceId: string): Record<string, string> {
  return {
    "Content-Type": "application/json",
    Accept: "application/json",
    "X-Workspace-Id": workspaceId,
  }
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  const text = await response.text()
  let body: unknown = null
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = { raw: text }
    }
  }

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${JSON.stringify(body)}`)
  }

  return body as T
}

export class LimiqClient {
  private readonly baseUrl: string
  private readonly workspaceId: string
  private readonly fetchImpl: typeof fetch

  constructor(options: LimiqClientOptions) {
    this.baseUrl = normalizeBaseUrl(options.baseUrl)
    this.workspaceId = options.workspaceId
    this.fetchImpl = options.fetchImpl ?? fetch
  }

  async requestCapability(input: RequestCapabilityInput): Promise<RequestCapabilityResponse> {
    const response = await this.fetchImpl(`${this.baseUrl}/capabilities/request`, {
      method: "POST",
      headers: buildHeaders(this.workspaceId),
      body: JSON.stringify({
        workspace_id: this.workspaceId,
        ...input,
      }),
    })

    return parseJsonResponse<RequestCapabilityResponse>(response)
  }

  async verifyAction(payload: VerifyRequestBody): Promise<VerifyResponse> {
    const response = await this.fetchImpl(`${this.baseUrl}/verify`, {
      method: "POST",
      headers: buildHeaders(this.workspaceId),
      body: JSON.stringify(payload),
    })

    return parseJsonResponse<VerifyResponse>(response)
  }
}

export function buildSignedRequest(input: BuildSignedRequestInput): VerifyRequestBody {
  const capabilityJti = extractCapabilityJti(input.capability_token)
  const signed = signAction({
    agent_id: input.agent_id,
    workspace_id: input.workspace_id,
    action_type: input.action_type,
    target_service: input.target_service,
    payload: input.payload,
    capability_jti: capabilityJti,
    privateKeyBase64: input.privateKeyBase64,
  })

  return {
    workspace_id: input.workspace_id,
    agent_id: input.agent_id,
    action_type: input.action_type,
    target_service: input.target_service,
    payload: input.payload,
    signature: signed.signatureBase64,
    capability_token: input.capability_token,
    request_context: input.request_context ?? {},
  }
}
