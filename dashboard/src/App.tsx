import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Landing from '@/pages/Landing';
import NewEmergency from '@/pages/NewEmergency';
import MissionControl from '@/pages/MissionControl';
import ReportPage from '@/pages/ReportPage';
import HistoryPage from '@/pages/HistoryPage';

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-void text-ink">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/new" element={<NewEmergency />} />
          <Route path="/run/:simId" element={<MissionControl />} />
          <Route path="/report/:simId" element={<ReportPage />} />
          <Route path="/history" element={<HistoryPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
