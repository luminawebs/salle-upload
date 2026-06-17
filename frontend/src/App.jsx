import React, { useState } from 'react';
import MoodleEngineView from './components/MoodleEngineView';
import DocumentReviewerView from './components/DocumentReviewerView';

export default function App() {
  const [activeTab, setActiveTab] = useState('moodle');

  return (
    <>
      {activeTab === 'moodle' && <MoodleEngineView setActiveTab={setActiveTab} />}
      {activeTab === 'reviewer' && <DocumentReviewerView setActiveTab={setActiveTab} />}
    </>
  );
}
