import { describe, expect, it } from 'vitest'

import { pluginServerRows } from './data/join'
import { localWay, localWord } from './derive'

describe('local connector runtime recovery', () => {
  it('labels a recovering plugin MCP server as reconnecting', () => {
    const [row] = pluginServerRows({
      runtime: [
        {
          name: 'plugin__server',
          transport: 'http',
          tools: 0,
          connected: false,
          disabled: false,
          status: 'reconnecting',
          source: 'plugin',
          plugin: 'plugin'
        }
      ],
      servers: [
        {
          name: 'plugin__server',
          transport: 'http',
          url: 'https://example.test/mcp',
          args: [],
          env: [],
          enabled: true,
          source: 'plugin',
          plugin: 'plugin'
        }
      ]
    })

    expect(row.status).toBe('reconnecting')
    const way = localWay(row)
    expect(way.state).toBe('connecting')
    expect(way.verb).toBeUndefined()
    expect(localWord(way)).toBe('serverReconnecting')
  })
})
