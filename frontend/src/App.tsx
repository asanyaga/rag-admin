import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import Home from './pages/Home'
import SignIn from './pages/SignIn'
import SignUp from './pages/SignUp'

function App() {
  return (
    <BrowserRouter>
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        <header style={{ padding: '1rem', borderBottom: '1px solid #ccc' }}>
          <nav style={{ display: 'flex', gap: '1rem' }}>
            <Link to="/">Home</Link>
            <Link to="/signin">Sign In</Link>
            <Link to="/signup">Sign Up</Link>
          </nav>
        </header>

        <main style={{ flex: 1, padding: '2rem' }}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/signin" element={<SignIn />} />
            <Route path="/signup" element={<SignUp />} />
          </Routes>
        </main>

        <footer style={{ padding: '1rem', borderTop: '1px solid #ccc', textAlign: 'center' }}>
          <p>RAG Admin v0.1.0</p>
        </footer>
      </div>
    </BrowserRouter>
  )
}

export default App
