import React, { useState } from 'react';
import MoodleEngineView from './components/MoodleEngineView';
import DocumentReviewerView from './components/DocumentReviewerView';
import AutomatizacionTrackerView from './components/AutomatizacionTrackerView';
import { AutomationProvider } from './context/AutomationContext';

export default function App() {
  const [activeTab, setActiveTab] = useState('tracker');

  return (
    <AutomationProvider>
      <div style={{ display: activeTab === 'tracker' ? 'block' : 'none', height: '100%' }}>
        <AutomatizacionTrackerView setActiveTab={setActiveTab} />
      </div>
      <div style={{ display: activeTab === 'moodle' ? 'block' : 'none', height: '100%' }}>
        <MoodleEngineView setActiveTab={setActiveTab} />
      </div>
      <div style={{ display: activeTab === 'reviewer' ? 'block' : 'none', height: '100%' }}>
        <DocumentReviewerView setActiveTab={setActiveTab} />
      </div>
    </AutomationProvider>
  );
}
