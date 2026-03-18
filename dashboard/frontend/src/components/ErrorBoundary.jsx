import { Component } from 'react'

/**
 * Catches React render errors and failed /bracket (or other) loading so the app
 * shows a message instead of a blank screen.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <h1>Something went wrong</h1>
          <p>An error occurred loading the dashboard. Try refreshing the page.</p>
          {this.state.error && (
            <pre className="error-boundary-detail">{this.state.error.message}</pre>
          )}
        </div>
      )
    }
    return this.props.children
  }
}
