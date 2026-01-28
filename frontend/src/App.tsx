import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import { PrivateRoute } from './components/PrivateRoute'
import { RootLayout } from './components/layout/RootLayout'
import { AppLayout } from './components/layout/AppLayout'
import SignInPage from './pages/SignInPage'
import SignUpPage from './pages/SignUpPage'
import AuthCallbackPage from './pages/AuthCallbackPage'
import HomePage from './pages/HomePage'
import ProjectsPage from './pages/ProjectsPage'
import DocumentsPage from './pages/DocumentsPage'
import IndexPage from './pages/IndexPage'
import SettingsPage from './pages/SettingsPage'

const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      {
        path: '/signin',
        element: <SignInPage />,
      },
      {
        path: '/signup',
        element: <SignUpPage />,
      },
      {
        path: '/auth/callback',
        element: <AuthCallbackPage />,
      },
      {
        path: '/',
        element: (
          <PrivateRoute>
            <AppLayout />
          </PrivateRoute>
        ),
        children: [
          {
            index: true,
            element: <HomePage />,
            handle: { breadcrumb: 'Home' },
          },
          {
            path: 'projects',
            element: <ProjectsPage />,
            handle: { breadcrumb: 'Projects' },
          },
          {
            path: 'documents',
            element: <DocumentsPage />,
            handle: { breadcrumb: 'Documents' },
          },
          {
            path: 'index',
            element: <IndexPage />,
            handle: { breadcrumb: 'Index' },
          },
          {
            path: 'settings',
            element: <SettingsPage />,
            handle: { breadcrumb: 'Settings' },
          },
        ],
      },
    ],
  },
])

function App() {
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  )
}

export default App
