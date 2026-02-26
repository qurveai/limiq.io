import { useMemo, useState } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { callApi } from "@/lib/api"
import type { PlaygroundRequest } from "@/lib/types"

const DEFAULT_PUBLIC_KEY = "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE="
const encoder = new TextEncoder()

function parseJsonInput(value: string): unknown {
  if (!value.trim()) {
    return {}
  }
  return JSON.parse(value) as unknown
}

function pretty(value: unknown): string {
  return JSON.stringify(value, null, 2)
}

function sortJsonValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => sortJsonValue(item))
  }

  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).sort(([a], [b]) => {
      if (a < b) {
        return -1
      }
      if (a > b) {
        return 1
      }
      return 0
    })
    const out: Record<string, unknown> = {}
    for (const [key, item] of entries) {
      out[key] = sortJsonValue(item)
    }
    return out
  }

  return value
}

function canonicalJsonString(payload: Record<string, unknown>): string {
  return JSON.stringify(sortJsonValue(payload))
}

function toBase64(bytes: Uint8Array): string {
  let binary = ""
  for (const byte of bytes) {
    binary += String.fromCharCode(byte)
  }
  return btoa(binary)
}

function fromBase64Url(input: string): string {
  const normalized = input.replace(/-/g, "+").replace(/_/g, "/")
  const padding = normalized.length % 4 === 0 ? "" : "=".repeat(4 - (normalized.length % 4))
  return atob(normalized + padding)
}

function extractJtiFromToken(token: string): string | null {
  const parts = token.split(".")
  if (parts.length < 2) {
    return null
  }

  try {
    const payloadRaw = fromBase64Url(parts[1])
    const payload = JSON.parse(payloadRaw) as Record<string, unknown>
    const jti = payload.jti
    return typeof jti === "string" ? jti : null
  } catch {
    return null
  }
}

function App() {
  const [baseUrl, setBaseUrl] = useState(
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  )
  const [bootstrapToken, setBootstrapToken] = useState(
    import.meta.env.VITE_BOOTSTRAP_TOKEN || "",
  )
  const [workspaceId, setWorkspaceId] = useState<string>(crypto.randomUUID())
  const [workspaceName, setWorkspaceName] = useState("Playground Workspace")
  const [workspaceSlug, setWorkspaceSlug] = useState("")
  const [workspaceLookupId, setWorkspaceLookupId] = useState("")

  const [agentId, setAgentId] = useState("")
  const [policyId, setPolicyId] = useState("")
  const [capabilityToken, setCapabilityToken] = useState("")

  const [agentName, setAgentName] = useState("agent-playground")
  const [publicKey, setPublicKey] = useState(DEFAULT_PUBLIC_KEY)
  const [devPrivateKey, setDevPrivateKey] = useState<CryptoKey | null>(null)

  const [policyName, setPolicyName] = useState("purchase_playground")
  const [policyVersion, setPolicyVersion] = useState("1")
  const [policyJson, setPolicyJson] = useState(
    pretty({
      allowed_tools: ["purchase"],
      spend: { currency: "EUR", max_per_tx: 50 },
      rate_limits: { max_actions_per_min: 10 },
    }),
  )

  const [capabilityAction, setCapabilityAction] = useState("purchase")
  const [capabilityTarget, setCapabilityTarget] = useState("stripe_proxy")
  const [capabilityScopes, setCapabilityScopes] = useState(pretty(["purchase"]))
  const [capabilityLimits, setCapabilityLimits] = useState(
    pretty({ amount: 18, currency: "EUR" }),
  )
  const [ttlMinutes, setTtlMinutes] = useState("15")

  const [verifyAction, setVerifyAction] = useState("purchase")
  const [verifyTarget, setVerifyTarget] = useState("stripe_proxy")
  const [verifyPayload, setVerifyPayload] = useState(
    pretty({ amount: 18, currency: "EUR", tool: "purchase" }),
  )
  const [verifySignature, setVerifySignature] = useState("")

  const [auditMode, setAuditMode] = useState<"events" | "export-json" | "export-csv">(
    "events",
  )
  const [decisionFilter, setDecisionFilter] = useState<"ALL" | "ALLOW" | "DENY">(
    "ALL",
  )

  const [history, setHistory] = useState<PlaygroundRequest[]>([])
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null)
  const [errorText, setErrorText] = useState("")

  async function generateDevKeypair() {
    setErrorText("")
    try {
      const keyPair = await crypto.subtle.generateKey(
        { name: "Ed25519" },
        true,
        ["sign", "verify"],
      )
      const publicRaw = await crypto.subtle.exportKey("raw", keyPair.publicKey)
      const publicB64 = toBase64(new Uint8Array(publicRaw))
      setPublicKey(publicB64)
      setDevPrivateKey(keyPair.privateKey)
      setVerifySignature("")
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to generate keypair"
      setErrorText(message)
    }
  }

  async function signVerifyRequest() {
    setErrorText("")
    try {
      if (!devPrivateKey) {
        throw new Error("Generate a dev keypair first")
      }
      if (!agentId.trim()) {
        throw new Error("Missing agent id")
      }
      if (!workspaceId.trim()) {
        throw new Error("Missing workspace id")
      }
      if (!capabilityToken.trim()) {
        throw new Error("Missing capability token")
      }

      const payload = parseJsonInput(verifyPayload)
      if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        throw new Error("Verify payload must be a JSON object")
      }

      const capabilityJti = extractJtiFromToken(capabilityToken)
      if (!capabilityJti) {
        throw new Error("Cannot extract capability jti from token")
      }

      const envelope: Record<string, unknown> = {
        agent_id: agentId,
        workspace_id: workspaceId,
        action_type: verifyAction,
        target_service: verifyTarget,
        payload,
        capability_jti: capabilityJti,
      }
      const canonical = canonicalJsonString(envelope)
      const digest = await crypto.subtle.digest("SHA-256", encoder.encode(canonical))
      const signatureBuffer = await crypto.subtle.sign("Ed25519", devPrivateKey, digest)
      setVerifySignature(toBase64(new Uint8Array(signatureBuffer)))
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to sign verify request"
      setErrorText(message)
    }
  }

  const selectedRequest = useMemo(
    () => history.find((item) => item.id === selectedRequestId) ?? history[0] ?? null,
    [history, selectedRequestId],
  )

  async function runRequest(params: {
    title: string
    method: "GET" | "POST"
    path: string
    body?: unknown
  }) {
    setErrorText("")
    try {
      const { request } = await callApi({
        title: params.title,
        baseUrl,
        workspaceId,
        bootstrapToken,
        method: params.method,
        path: params.path,
        body: params.body,
      })
      setHistory((prev) => [request, ...prev].slice(0, 20))
      setSelectedRequestId(request.id)

      const data = request.responseBody as Record<string, unknown> | null
      if (params.title === "Create Agent" && request.ok && data?.id) {
        setAgentId(String(data.id))
      }
      if (params.title === "Create Policy" && request.ok && data?.id) {
        setPolicyId(String(data.id))
      }
      if (params.title === "Request Capability" && request.ok && data?.token) {
        setCapabilityToken(String(data.token))
      }
      if (
        (params.title === "Create Workspace" || params.title === "Get Workspace") &&
        request.ok &&
        data?.id
      ) {
        const nextWorkspaceId = String(data.id)
        setWorkspaceId(nextWorkspaceId)
        setWorkspaceLookupId(nextWorkspaceId)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error"
      setErrorText(message)
    }
  }

  return (
    <main className="min-h-screen p-4 md:p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="bg-grid rounded-xl border border-border/70 bg-card/60 p-6 backdrop-blur">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h1 className="text-3xl font-semibold">Limiq.io API Playground</h1>
              <p className="text-sm text-muted-foreground">
                Internal test bench for backend flows. Uses live API responses and keeps the last
                20 requests.
              </p>
            </div>
            <Badge variant="secondary">internal tool</Badge>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                API Base URL
              </label>
              <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                X-Workspace-Id
              </label>
              <Input value={workspaceId} onChange={(e) => setWorkspaceId(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                X-Bootstrap-Token
              </label>
              <Input
                type="password"
                placeholder="required for POST /workspaces"
                value={bootstrapToken}
                onChange={(e) => setBootstrapToken(e.target.value)}
              />
            </div>
          </div>
        </header>

        {errorText ? (
          <Alert variant="destructive">
            <AlertTitle>Request Error</AlertTitle>
            <AlertDescription>{errorText}</AlertDescription>
          </Alert>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-[1.25fr_1fr]">
          <Card className="border-border/70 bg-card/80">
            <CardHeader>
              <CardTitle>API Actions</CardTitle>
              <CardDescription>
                Trigger endpoint calls with editable payloads. IDs are auto-filled from successful
                responses.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="agents" className="w-full">
                <TabsList className="grid w-full grid-cols-6">
                  <TabsTrigger value="workspace">Workspace</TabsTrigger>
                  <TabsTrigger value="agents">Agents</TabsTrigger>
                  <TabsTrigger value="policy">Policy</TabsTrigger>
                  <TabsTrigger value="capability">Capability</TabsTrigger>
                  <TabsTrigger value="verify">Verify</TabsTrigger>
                  <TabsTrigger value="audit">Audit</TabsTrigger>
                </TabsList>

                <TabsContent value="workspace" className="space-y-4 pt-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <Input
                      placeholder="workspace name"
                      value={workspaceName}
                      onChange={(e) => setWorkspaceName(e.target.value)}
                    />
                    <Input
                      placeholder="workspace slug (optional)"
                      value={workspaceSlug}
                      onChange={(e) => setWorkspaceSlug(e.target.value)}
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      onClick={() =>
                        runRequest({
                          title: "Create Workspace",
                          method: "POST",
                          path: "/workspaces",
                          body: {
                            name: workspaceName,
                            ...(workspaceSlug.trim() ? { slug: workspaceSlug.trim() } : {}),
                          },
                        })
                      }
                    >
                      Create Workspace
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={!workspaceLookupId}
                      onClick={() =>
                        runRequest({
                          title: "Get Workspace",
                          method: "GET",
                          path: `/workspaces/${workspaceLookupId}`,
                        })
                      }
                    >
                      Get Workspace
                    </Button>
                  </div>
                  <Input
                    placeholder="workspace id"
                    value={workspaceLookupId}
                    onChange={(e) => setWorkspaceLookupId(e.target.value)}
                  />
                </TabsContent>

                <TabsContent value="agents" className="space-y-4 pt-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <Input
                      placeholder="agent name"
                      value={agentName}
                      onChange={(e) => setAgentName(e.target.value)}
                    />
                    <Input
                      placeholder="base64 public key"
                      value={publicKey}
                      onChange={(e) => setPublicKey(e.target.value)}
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      onClick={() =>
                        runRequest({
                          title: "Create Agent",
                          method: "POST",
                          path: "/agents",
                          body: {
                            workspace_id: workspaceId,
                            name: agentName,
                            public_key: publicKey,
                            metadata: {},
                          },
                        })
                      }
                    >
                      Create Agent
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={!agentId}
                      onClick={() =>
                        runRequest({
                          title: "Get Agent",
                          method: "GET",
                          path: `/agents/${agentId}`,
                        })
                      }
                    >
                      Get Agent
                    </Button>
                    <Button
                      variant="destructive"
                      disabled={!agentId}
                      onClick={() =>
                        runRequest({
                          title: "Revoke Agent",
                          method: "POST",
                          path: `/agents/${agentId}/revoke`,
                          body: { workspace_id: workspaceId, reason: "playground_revoke" },
                        })
                      }
                    >
                      Revoke Agent
                    </Button>
                  </div>
                  <Input
                    placeholder="agent id"
                    value={agentId}
                    onChange={(e) => setAgentId(e.target.value)}
                  />
                </TabsContent>

                <TabsContent value="policy" className="space-y-4 pt-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <Input
                      placeholder="policy name"
                      value={policyName}
                      onChange={(e) => setPolicyName(e.target.value)}
                    />
                    <Input
                      placeholder="version"
                      value={policyVersion}
                      onChange={(e) => setPolicyVersion(e.target.value)}
                    />
                  </div>
                  <Textarea
                    rows={8}
                    value={policyJson}
                    onChange={(e) => setPolicyJson(e.target.value)}
                  />
                  <div className="flex flex-wrap gap-2">
                    <Button
                      onClick={() =>
                        runRequest({
                          title: "Create Policy",
                          method: "POST",
                          path: "/policies",
                          body: {
                            workspace_id: workspaceId,
                            name: policyName,
                            version: Number(policyVersion),
                            schema_version: 1,
                            policy_json: parseJsonInput(policyJson),
                          },
                        })
                      }
                    >
                      Create Policy
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={!agentId || !policyId}
                      onClick={() =>
                        runRequest({
                          title: "Bind Policy",
                          method: "POST",
                          path: `/agents/${agentId}/bind_policy`,
                          body: { workspace_id: workspaceId, policy_id: policyId },
                        })
                      }
                    >
                      Bind Policy
                    </Button>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <Input
                      placeholder="agent id"
                      value={agentId}
                      onChange={(e) => setAgentId(e.target.value)}
                    />
                    <Input
                      placeholder="policy id"
                      value={policyId}
                      onChange={(e) => setPolicyId(e.target.value)}
                    />
                  </div>
                </TabsContent>

                <TabsContent value="capability" className="space-y-4 pt-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <Input
                      placeholder="action"
                      value={capabilityAction}
                      onChange={(e) => setCapabilityAction(e.target.value)}
                    />
                    <Input
                      placeholder="target service"
                      value={capabilityTarget}
                      onChange={(e) => setCapabilityTarget(e.target.value)}
                    />
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <Textarea
                      rows={5}
                      value={capabilityScopes}
                      onChange={(e) => setCapabilityScopes(e.target.value)}
                    />
                    <Textarea
                      rows={5}
                      value={capabilityLimits}
                      onChange={(e) => setCapabilityLimits(e.target.value)}
                    />
                  </div>
                  <div className="grid gap-3 md:grid-cols-[1fr_auto]">
                    <Input
                      placeholder="agent id"
                      value={agentId}
                      onChange={(e) => setAgentId(e.target.value)}
                    />
                    <Input
                      placeholder="ttl minutes"
                      value={ttlMinutes}
                      onChange={(e) => setTtlMinutes(e.target.value)}
                    />
                  </div>
                  <Button
                    disabled={!agentId}
                    onClick={() =>
                      runRequest({
                        title: "Request Capability",
                        method: "POST",
                        path: "/capabilities/request",
                        body: {
                          workspace_id: workspaceId,
                          agent_id: agentId,
                          action: capabilityAction,
                          target_service: capabilityTarget,
                          requested_scopes: parseJsonInput(capabilityScopes),
                          requested_limits: parseJsonInput(capabilityLimits),
                          ttl_minutes: Number(ttlMinutes),
                        },
                      })
                    }
                  >
                    Request Capability
                  </Button>
                  <Textarea
                    rows={4}
                    placeholder="capability token"
                    value={capabilityToken}
                    onChange={(e) => setCapabilityToken(e.target.value)}
                  />
                </TabsContent>

                <TabsContent value="verify" className="space-y-4 pt-4">
                  <div className="rounded-md border border-border/70 bg-muted/40 p-3">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <Badge variant={devPrivateKey ? "secondary" : "outline"}>
                        {devPrivateKey ? "dev key loaded" : "no dev key"}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        Dev helper: generate keypair, sign payload, then verify.
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button variant="secondary" onClick={generateDevKeypair}>
                        Generate Dev Keypair
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() =>
                          setVerifyPayload(
                            pretty({ amount: 18, currency: "EUR", tool: "purchase" }),
                          )
                        }
                      >
                        Preset ALLOW
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() =>
                          setVerifyPayload(
                            pretty({ amount: 999, currency: "EUR", tool: "purchase" }),
                          )
                        }
                      >
                        Preset DENY Spend
                      </Button>
                      <Button variant="secondary" onClick={signVerifyRequest}>
                        Sign Verify Request
                      </Button>
                    </div>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2">
                    <Input
                      placeholder="action type"
                      value={verifyAction}
                      onChange={(e) => setVerifyAction(e.target.value)}
                    />
                    <Input
                      placeholder="target service"
                      value={verifyTarget}
                      onChange={(e) => setVerifyTarget(e.target.value)}
                    />
                  </div>
                  <Textarea
                    rows={6}
                    value={verifyPayload}
                    onChange={(e) => setVerifyPayload(e.target.value)}
                  />
                  <Textarea
                    rows={4}
                    placeholder="base64 signature"
                    value={verifySignature}
                    onChange={(e) => setVerifySignature(e.target.value)}
                  />
                  <Textarea
                    rows={4}
                    placeholder="capability token"
                    value={capabilityToken}
                    onChange={(e) => setCapabilityToken(e.target.value)}
                  />
                  <Button
                    disabled={!agentId || !capabilityToken || !verifySignature}
                    onClick={() =>
                      runRequest({
                        title: "Verify Action",
                        method: "POST",
                        path: "/verify",
                        body: {
                          workspace_id: workspaceId,
                          agent_id: agentId,
                          action_type: verifyAction,
                          target_service: verifyTarget,
                          payload: parseJsonInput(verifyPayload),
                          signature: verifySignature,
                          capability_token: capabilityToken,
                          request_context: {},
                        },
                      })
                    }
                  >
                    Verify Action
                  </Button>
                </TabsContent>

                <TabsContent value="audit" className="space-y-4 pt-4">
                  <div className="grid gap-3 md:grid-cols-[1fr_auto_auto]">
                    <Select
                      value={auditMode}
                      onValueChange={(value) =>
                        setAuditMode(value as "events" | "export-json" | "export-csv")
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="events">/audit/events</SelectItem>
                        <SelectItem value="export-json">/audit/export.json</SelectItem>
                        <SelectItem value="export-csv">/audit/export.csv</SelectItem>
                      </SelectContent>
                    </Select>
                    <Select
                      value={decisionFilter}
                      onValueChange={(value) => setDecisionFilter(value as "ALL" | "ALLOW" | "DENY")}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ALL">All decisions</SelectItem>
                        <SelectItem value="ALLOW">ALLOW</SelectItem>
                        <SelectItem value="DENY">DENY</SelectItem>
                      </SelectContent>
                    </Select>
                    <Button
                      onClick={() => {
                        const basePath =
                          auditMode === "events"
                            ? "/audit/events"
                            : auditMode === "export-json"
                              ? "/audit/export.json"
                              : "/audit/export.csv"

                        const search = new URLSearchParams({ workspace_id: workspaceId })
                        if (decisionFilter !== "ALL") {
                          search.set("decision", decisionFilter)
                        }

                        runRequest({
                          title: `Audit ${auditMode}`,
                          method: "GET",
                          path: `${basePath}?${search.toString()}`,
                        })
                      }}
                    >
                      Run Audit Query
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="secondary"
                      onClick={() =>
                        runRequest({
                          title: "Audit Integrity",
                          method: "GET",
                          path: `/audit/integrity/check?workspace_id=${workspaceId}`,
                        })
                      }
                    >
                      Check Integrity
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() =>
                        runRequest({
                          title: "Metrics",
                          method: "GET",
                          path: "/metrics",
                        })
                      }
                    >
                      Read Metrics
                    </Button>
                  </div>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>

          <div className="space-y-6">
            <Card className="border-border/70 bg-card/80">
              <CardHeader>
                <CardTitle>Latest Response</CardTitle>
                <CardDescription>
                  Status, duration, and parsed payload from the selected request.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {selectedRequest ? (
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={selectedRequest.ok ? "secondary" : "destructive"}>
                        {selectedRequest.status}
                      </Badge>
                      <Badge variant="outline">{selectedRequest.durationMs}ms</Badge>
                      <span className="text-xs text-muted-foreground">{selectedRequest.method}</span>
                      <span className="truncate text-xs text-muted-foreground">
                        {selectedRequest.url}
                      </span>
                    </div>
                    <pre className="max-h-[360px] overflow-auto rounded-md bg-muted p-3 text-xs">
                      {pretty(selectedRequest.responseBody)}
                    </pre>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No request sent yet.</p>
                )}
              </CardContent>
            </Card>

            <Card className="border-border/70 bg-card/80">
              <CardHeader>
                <CardTitle>Recent Requests</CardTitle>
                <CardDescription>Click a row to inspect its response payload.</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Action</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Duration</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {history.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={3} className="text-muted-foreground">
                          No requests yet.
                        </TableCell>
                      </TableRow>
                    ) : (
                      history.map((item) => (
                        <TableRow
                          key={item.id}
                          className="cursor-pointer"
                          onClick={() => setSelectedRequestId(item.id)}
                        >
                          <TableCell>{item.title}</TableCell>
                          <TableCell>
                            <Badge variant={item.ok ? "secondary" : "destructive"}>
                              {item.status}
                            </Badge>
                          </TableCell>
                          <TableCell>{item.durationMs}ms</TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </main>
  )
}

export default App
