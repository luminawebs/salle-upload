import React from 'react';

export default function NavigationTabs({ activeTab, setActiveTab }) {
  return (
    <div className="flex space-x-1 bg-background p-1 rounded-lg border border-border">
      <button 
        onClick={() => setActiveTab('tracker')}
        className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${activeTab === 'tracker' ? 'bg-primary text-white shadow' : 'text-gray-400 hover:text-white hover:bg-surface'}`}
      >
        Tracker (Nuevo)
      </button>
      <button 
        onClick={() => setActiveTab('moodle')}
        className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${activeTab === 'moodle' ? 'bg-primary text-white shadow' : 'text-gray-400 hover:text-white hover:bg-surface'}`}
      >
        Automatización (Clásica)
      </button>
      <button 
        onClick={() => setActiveTab('reviewer')}
        className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${activeTab === 'reviewer' ? 'bg-primary text-white shadow' : 'text-gray-400 hover:text-white hover:bg-surface'}`}
      >
        Revisor de Documentos
      </button>
    </div>
  );
}
