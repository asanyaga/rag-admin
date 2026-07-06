import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
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
import DocumentsPage from './pages/DocumentsPage'
import SourceDocumentsPage from './pages/SourceDocumentsPage'
import IndexPage from './pages/IndexPage'
import CreateIndexPage from './pages/CreateIndexPage'
import IndexDetailPage from './pages/IndexDetailPage'
import SettingsPage from './pages/SettingsPage'
import RetrievalEvaluationPage from './pages/RetrievalEvaluationPage'
import ExtractionEvaluationPage from './pages/ExtractionEvaluationPage'
import ParserEvaluationPage from './pages/ParserEvaluationPage'
import GoldenSetEditorPage from './pages/GoldenSetEditorPage'
import NewEvalRunPage from './pages/NewEvalRunPage'
import EvalRunDetailPage from './pages/EvalRunDetailPage'
import EvalResultDetailPage from './pages/EvalResultDetailPage'
import RunComparisonPage from './pages/RunComparisonPage'
import ExperimentDetailPage from './pages/ExperimentDetailPage'
import ExperimentComparisonPage from './pages/ExperimentComparisonPage'
import ExtractionPage from './pages/ExtractionPage'
import NewExtractionRunPage from './pages/NewExtractionRunPage'
import ExtractionResultDetailPage from './pages/ExtractionResultDetailPage'
import AgentListPage from './pages/AgentListPage'
import AgentComposerPage from './pages/AgentComposerPage'
import AgentRunsPage from './pages/AgentRunsPage'
import AgentRunDetailPage from './pages/AgentRunDetailPage'
import DataStoresPage from './pages/DataStoresPage'
import DataStoreDetailPage from './pages/DataStoreDetailPage'
import ExportPlaygroundPage from './pages/ExportPlaygroundPage'
import { ParseRunDetailPage } from './pages/ParseRunDetailPage'
import ClassificationPage from './pages/ClassificationPage'
import { NewClassificationRunPage } from './pages/NewClassificationRunPage'
import { ClassificationRunDetailPage } from './pages/ClassificationRunDetailPage'

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
            path: 'parse',
            element: <DocumentsPage />,
            handle: { breadcrumb: 'Parse' },
          },
          {
            path: 'source-documents',
            element: <SourceDocumentsPage />,
            handle: { breadcrumb: 'Source Documents' },
          },
          {
            path: 'parse/:documentId/runs/:runId',
            element: <ParseRunDetailPage />,
            handle: { breadcrumb: 'Parse Run' },
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
            path: 'extract',
            element: <ExtractionPage />,
            handle: { breadcrumb: 'Extract' },
          },
          {
            path: 'extract/new',
            element: <NewExtractionRunPage />,
            handle: { breadcrumb: 'New Extraction Run' },
          },
          {
            path: 'extract/:resultId',
            element: <ExtractionResultDetailPage />,
            handle: { breadcrumb: 'Extraction Result' },
          },
          {
            path: 'classify',
            element: <ClassificationPage />,
            handle: { breadcrumb: 'Classify' },
          },
          {
            path: 'classify/new',
            element: <NewClassificationRunPage />,
            handle: { breadcrumb: 'New Classification Run' },
          },
          {
            path: 'classify/:runId',
            element: <ClassificationRunDetailPage />,
            handle: { breadcrumb: 'Classification Run' },
          },
          {
            path: 'data-stores',
            element: <DataStoresPage />,
            handle: { breadcrumb: 'Data Stores' },
          },
          {
            path: 'data-stores/:storeId',
            element: <DataStoreDetailPage />,
            handle: { breadcrumb: 'Data Store Detail' },
          },
          {
            path: 'export',
            element: <ExportPlaygroundPage />,
            handle: { breadcrumb: 'Export' },
          },
          {
            path: 'agent',
            element: <AgentListPage />,
            handle: { breadcrumb: 'Agents' },
          },
          {
            path: 'agent/new',
            element: <AgentComposerPage />,
            handle: { breadcrumb: 'New Agent' },
          },
          {
            path: 'agent/:agentId',
            element: <AgentComposerPage />,
            handle: { breadcrumb: 'Edit Agent' },
          },
          {
            path: 'agent/:agentId/runs',
            element: <AgentRunsPage />,
            handle: { breadcrumb: 'Agent Runs' },
          },
          {
            path: 'agent/runs/:runId',
            element: <AgentRunDetailPage />,
            handle: { breadcrumb: 'Run Detail' },
          },
{
            path: 'evaluation',
            element: <Navigate to="/evaluation/retrieval" replace />,
          },
          {
            path: 'evaluation/retrieval',
            element: <RetrievalEvaluationPage />,
            handle: { breadcrumb: 'Retrieval Evaluation' },
          },
          {
            path: 'evaluation/extraction',
            element: <ExtractionEvaluationPage />,
            handle: { breadcrumb: 'Extraction Evaluation' },
          },
          {
            path: 'evaluation/parser',
            element: <ParserEvaluationPage />,
            handle: { breadcrumb: 'Parser Evaluation' },
          },
          {
            path: 'evaluation/golden-sets/:goldenSetId',
            element: <GoldenSetEditorPage />,
            handle: { breadcrumb: 'Golden Set Editor' },
          },
          {
            path: 'evaluation/experiments/:experimentId',
            element: <ExperimentDetailPage />,
            handle: { breadcrumb: 'Experiment Detail' },
          },
          {
            path: 'evaluation/experiments/:experimentId/compare',
            element: <ExperimentComparisonPage />,
            handle: { breadcrumb: 'Experiment Comparison' },
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
