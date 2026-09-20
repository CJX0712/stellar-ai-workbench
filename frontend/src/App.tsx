// Author: 晨星
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { ChatPage } from './pages/ChatPage'
import { KnowledgePage } from './pages/KnowledgePage'
import { AgentsPage } from './pages/AgentsPage'
import { SettingsPage } from './pages/SettingsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<ChatPage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
