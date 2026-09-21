import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import ImageSearchPage from './pages/ImageSearchPage'
import TextSearchPage from './pages/TextSearchPage'
import ResultsPage from './pages/ResultsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/search/image" element={<ImageSearchPage />} />
        <Route path="/search/text" element={<TextSearchPage />} />
        <Route path="/results" element={<ResultsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
