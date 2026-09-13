import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { CompanyProvider } from './lib/company'
import Layout from './components/Layout'
import Home from './pages/Home'
import Lines from './pages/Lines'
import Upcoming from './pages/Upcoming'
import Attention from './pages/Attention'
import Upload from './pages/Upload'

export default function App() {
  return (
    <BrowserRouter>
      <CompanyProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Home />} />
            <Route path="/lines" element={<Lines />} />
            <Route path="/upcoming" element={<Upcoming />} />
            <Route path="/attention" element={<Attention />} />
            <Route path="/upload" element={<Upload />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </CompanyProvider>
    </BrowserRouter>
  )
}
