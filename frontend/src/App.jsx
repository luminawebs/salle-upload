import React, { useState } from 'react';
import MoodleEngineView from './components/MoodleEngineView';
import DocumentReviewerView from './components/DocumentReviewerView';
import AutomatizacionTrackerView from './components/AutomatizacionTrackerView';

export default function App() {
  const [activeTab, setActiveTab] = useState('tracker');

  return (
    <>
      {activeTab === 'tracker' && <AutomatizacionTrackerView setActiveTab={setActiveTab} />}
      {activeTab === 'moodle' && <MoodleEngineView setActiveTab={setActiveTab} />}
      {activeTab === 'reviewer' && <DocumentReviewerView setActiveTab={setActiveTab} />}
    </>
  );
}
