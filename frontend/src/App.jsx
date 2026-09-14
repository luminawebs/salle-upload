import React from 'react';
import AutomationView from './components/AutomationView';
import { AutomationProvider } from './context/AutomationContext';
import GlobalPopupModal from './components/GlobalPopupModal';

export default function App() {
  return (
    <AutomationProvider>
      <AutomationView />
      <GlobalPopupModal />
    </AutomationProvider>
  );
}
