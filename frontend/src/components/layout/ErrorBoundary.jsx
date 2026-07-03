import { Component } from 'react'

/**
 * Catches render errors in the page tree and shows a recoverable message
 * instead of a blank white screen. Resets when the route (key) changes.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // Surface the details in the dev console for debugging.
    console.error('Render error caught by ErrorBoundary:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center justify-center py-20 text-center gap-4">
          <p className="text-lg font-semibold text-red-400">Something went wrong on this page.</p>
          <p className="text-sm text-muted max-w-md break-words">{String(this.state.error?.message || this.state.error)}</p>
          <div className="flex gap-3">
            <button
              onClick={() => this.setState({ error: null })}
              className="px-4 py-2 rounded-btn text-sm text-white"
              style={{ background: 'rgba(129,140,248,0.25)', border: '1px solid rgba(129,140,248,0.4)' }}
            >
              Try again
            </button>
            <button
              onClick={() => { window.location.href = '/' }}
              className="px-4 py-2 rounded-btn text-sm text-muted"
              style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)' }}
            >
              Back to dashboard
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
