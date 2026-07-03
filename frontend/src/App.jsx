import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import HoloBrainBackground from './components/background/HoloBrainBackground'
import ErrorBoundary from './components/layout/ErrorBoundary'
import Sidebar from './components/layout/Sidebar'
import Navbar from './components/layout/Navbar'
import Dashboard from './pages/Dashboard'
import Patients from './pages/Patients'
import PatientProfile from './pages/PatientProfile'
import ScanUpload from './pages/ScanUpload'
import MRIToPET from './pages/MRIToPET'
import CognitiveTest from './pages/CognitiveTest'
import PredictionResult from './pages/PredictionResult'
import DigitalTwin from './pages/DigitalTwin'
import ReportUpload from './pages/ReportUpload'

export default function App() {
  return (
    <BrowserRouter>
      {/* Fixed aurora + holographic brain background */}
      <HoloBrainBackground />

      {/* App shell — sits above the fixed background */}
      <div className="relative z-10 flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex flex-col flex-1 overflow-hidden">
          <Navbar />
          <main className="flex-1 overflow-y-auto">
            <ErrorBoundary>
            <AnimatePresence mode="wait">
              <Routes>
                <Route path="/"                          element={<Dashboard />} />
                <Route path="/patients"                  element={<Patients />} />
                <Route path="/patient/:id"               element={<PatientProfile />} />
                <Route path="/patient/:id/scan"          element={<ScanUpload />} />
                <Route path="/patient/:id/mri-to-pet"   element={<MRIToPET />} />
                <Route path="/patient/:id/cognitive"     element={<CognitiveTest />} />
                <Route path="/patient/:id/prediction"    element={<PredictionResult />} />
                <Route path="/patient/:id/twin"          element={<DigitalTwin />} />
                <Route path="/patient/:id/reports"       element={<ReportUpload />} />
              </Routes>
            </AnimatePresence>
            </ErrorBoundary>
          </main>
        </div>
      </div>
    </BrowserRouter>
  )
}
