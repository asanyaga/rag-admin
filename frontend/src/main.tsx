import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { initializeTracing } from '@/lib/tracing'

// Initialize OpenTelemetry tracing BEFORE React app renders
// This ensures all HTTP requests and user interactions are traced
initializeTracing()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
