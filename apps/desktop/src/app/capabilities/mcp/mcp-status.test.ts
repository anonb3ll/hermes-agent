import { describe, expect, it } from 'vitest'

import { canAuthenticate, statusOf } from './mcp-status'

const server = { auth: 'oauth', url: 'https://example.test/mcp' }

describe('MCP status after a hub restart', () => {
  it('shows a lost transport session as reconnecting without offering sign-in', () => {
    const status = statusOf(server, { ok: false, error: 'OAuth transport: Session not found', tools: [] })

    expect(status).toBe('reconnecting')
    expect(canAuthenticate(server, status)).toBe(false)
  })

  it('continues to show a real 401 as needing authentication', () => {
    const status = statusOf(server, { ok: false, error: 'HTTP 401 Unauthorized', tools: [] })

    expect(status).toBe('needs-auth')
    expect(canAuthenticate(server, status)).toBe(true)
  })
})
