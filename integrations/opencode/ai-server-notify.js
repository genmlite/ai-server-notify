/**
 * Forward top-level OpenCode session state to ai-notify.
 * Child sessions are intentionally ignored to avoid sub-agent completion noise.
 */
const DEFAULT_NOTIFIER = `${process.env.HOME}/.local/bin/ai-notify`
const INTERESTING_EVENTS = new Set([
  "session.idle",
  "session.deleted",
  "session.error",
  "permission.asked",
  "permission.updated",
  "permission.v2.asked",
  "question.asked",
  "question.v2.asked",
])

function sessionId(event) {
  const properties = event.properties || {}
  return properties.sessionID || properties.sessionId || properties.info?.id
}

function eventPayload(event, session, directory) {
  const properties = event.properties || {}
  return {
    event_type: event.type,
    cwd: session?.directory || directory,
    directory,
    session_id: session?.id || sessionId(event),
    session: session
      ? { id: session.id, title: session.title, directory: session.directory, parentID: session.parentID }
      : undefined,
    status: properties.status,
    error: properties.error,
    permission: properties.permission || properties.action || properties.type,
    questions: properties.questions,
  }
}

export default async function AiServerNotify({ client, directory, $ }, options = {}) {
  const notifier = String(options.notifier || DEFAULT_NOTIFIER)
  return {
    async event({ event }) {
      if (!INTERESTING_EVENTS.has(event.type)) return
      const id = sessionId(event)
      if (!id) return

      let session = event.properties?.info
      if (!session) {
        try {
          const result = await client.session.get({ path: { id }, query: { directory } })
          session = result.data
        } catch {
          // A session can disappear while its final event is being delivered.
        }
      }
      if (session?.parentID) return

      const payload = JSON.stringify(eventPayload(event, session, directory))
      await $.throws(false)`${$.escape(notifier)} opencode ${$.escape(payload)}`.quiet()
    },
  }
}
