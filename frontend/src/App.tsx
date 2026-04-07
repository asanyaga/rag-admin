import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import { ProjectProvider } from './contexts/ProjectContext'
import { PrivateRoute } from './components/PrivateRoute'
import { RootLayout } from './components/layout/RootLayout'
import { AppLayout } from './components/layout/AppLayout'
import SignInPage from './pages/SignInPage'
import SignUpPage from './pages/SignUpPage'
import AuthCallbackPage from './pages/AuthCallbackPage'
import DashboardPage from './pages/DashboardPage'
import ProjectsPage from './pages/ProjectsPage'
import ProjectDocumentsPage from './pages/ProjectDocumentsPage'
import DocumentsPage from './pages/DocumentsPage'
import IndexPage from './pages/IndexPage'
import CreateIndexPage from './pages/CreateIndexPage'
import IndexDetailPage from './pages/IndexDetailPage'
import SettingsPage from './pages/SettingsPage'
import EvaluationPage from './pages/EvaluationPage'
import GoldenSetEditorPage from './pages/GoldenSetEditorPage'
import GoldenSetGeneratePage from './pages/GoldenSetGeneratePage'
import NewEvalRunPage from './pages/NewEvalRunPage'
import EvalRunDetailPage from './pages/EvalRunDetailPage'
import EvalResultDetailPage from './pages/EvalResultDetailPage'
import RunComparisonPage from './pages/RunComparisonPage'
import ExperimentDetailPage from './pages/ExperimentDetailPage'
import ExtractionPage from './pages/ExtractionPage'

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
            element: <DashboardPage />,
            handle: { breadcrumb: 'Dashboard' },
          },
          {
            path: 'projects',
            element: <ProjectsPage />,
            handle: { breadcrumb: 'Projects' },
          },
          {
            path: 'projects/:projectId/documents',
            element: <ProjectDocumentsPage />,
            handle: { breadcrumb: 'Documents' },
          },
          {
            path: 'documents',
            element: <DocumentsPage />,
            handle: { breadcrumb: 'Documents' },
          },
          {
            path: 'index',
            element: <IndexPage />,
            handle: { breadcrumb: 'Indexes' },
          },
          {
            path: 'index/create',
            element: <CreateIndexPage />,
            handle: { breadcrumb: 'Create Index' },
          },
          {
            path: 'index/:indexId',
            element: <IndexDetailPage />,
            handle: { breadcrumb: 'Index Details' },
          },
          {
            path: 'extraction',
            element: <ExtractionPage />,
            handle: { breadcrumb: 'Extraction' },
          },
{
            path: 'evaluation',
            element: <EvaluationPage />,
            handle: { breadcrumb: 'Evaluation' },
          },
          {
            path: 'evaluation/golden-sets/:goldenSetId',
            element: <GoldenSetEditorPage />,
            handle: { breadcrumb: 'Golden Set Editor' },
          },
          {
            path: 'evaluation/golden-sets/:goldenSetId/generate',
            element: <GoldenSetGeneratePage />,
            handle: { breadcrumb: 'Auto-Generate' },
          },
          {
            path: 'evaluation/experiments/:experimentId',
            element: <ExperimentDetailPage />,
            handle: { breadcrumb: 'Experiment Detail' },
          },
          {
            path: 'evaluation/runs/new',
            element: <NewEvalRunPage />,
            handle: { breadcrumb: 'New Eval Run' },
          },
          {
            path: 'evaluation/runs/:runId',
            element: <EvalRunDetailPage />,
            handle: { breadcrumb: 'Eval Run Detail' },
          },
          {
            path: 'evaluation/runs/:runId/results/:resultId',
            element: <EvalResultDetailPage />,
            handle: { breadcrumb: 'Result Detail' },
          },
          {
            path: 'evaluation/compare',
            element: <RunComparisonPage />,
            handle: { breadcrumb: 'Run Comparison' },
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
      <ProjectProvider>
        <RouterProvider router={router} />
      </ProjectProvider>
    </AuthProvider>
  )
}

export default App
