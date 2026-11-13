import { Component, StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

class AppErrorBoundary extends Component {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error) {
    console.error('Driveboard could not render:', error)
  }

  render() {
    if (this.state.hasError) {
      return <main className="app-crash-fallback"><section><h1>Driveboard could not load</h1><p>Reload the page. If this keeps happening, share the browser console error with an SPC.</p><button onClick={() => window.location.reload()}>Reload Driveboard</button></section></main>
    }
    return this.props.children
  }
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((error) => {
      console.error('Driveboard service worker registration failed:', error)
    })
  })
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AppErrorBoundary><App /></AppErrorBoundary>
  </StrictMode>,
)
