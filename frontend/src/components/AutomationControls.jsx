import React, { useContext } from 'react';
import { AutomationContext } from '../context/AutomationContext';
import { Settings, Save, Check, Play } from 'lucide-react';

export default function AutomationControls() {
  const {
    settings,
    handleSetSetting,
    handleSaveSettings,
    isSaved,
    status,
    handleRun,
    handleStop
  } = useContext(AutomationContext);

  const isRunning = status === 'Running';

  return (
    <div className="bg-surface rounded-xl border border-border shadow-sm p-5">
      <div className="flex items-center space-x-3 mb-5">
        <div className="p-2.5 rounded-lg bg-primary/10 border border-primary/20">
          <Settings className="w-5 h-5 text-primary" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-white uppercase tracking-wider">Flujos Globales</h2>
          <p className="text-xs text-gray-400 mt-1">Configuración detallada del pipeline</p>
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex flex-col space-y-1">
          <label className="text-xs font-semibold text-gray-300 uppercase tracking-wide">ID de Curso(s)</label>
          <input
            type="text"
            value={settings.COURSES_TO_PROCESS}
            onChange={(e) => handleSetSetting('COURSES_TO_PROCESS', e.target.value)}
            disabled={isRunning}
            className="w-full bg-surface/50 border border-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-primary transition-colors disabled:opacity-50"
            placeholder="Ej: 70801, 70802"
          />
        </div>

        <div className="flex flex-col gap-2">
          {!isRunning ? (
            <button
              onClick={() => handleRun(handleSaveSettings)}
              className="w-full py-2.5 px-4 rounded-lg font-semibold flex items-center justify-center transition-all bg-primary hover:bg-primary-hover text-white shadow-lg shadow-primary/20 hover:shadow-primary/40 hover:-translate-y-0.5 text-sm"
            >
              <Play className="w-4 h-4 mr-2" />
              Iniciar Automatización
            </button>
          ) : (
            <button
              onClick={handleStop}
              className="w-full py-2.5 px-4 rounded-lg font-semibold flex items-center justify-center transition-all bg-red-600 hover:bg-red-500 text-white shadow-lg shadow-red-600/20 hover:shadow-red-500/40 hover:-translate-y-0.5 text-sm"
            >
              <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
              </svg>
              Detener Ejecución
            </button>
          )}

          <button
            onClick={handleSaveSettings}
            className="flex items-center py-2 hover:bg-gray-800 rounded-lg transition text-xs justify-center w-full font-medium border border-transparent hover:border-border"
          >
            {isSaved ? <Check className="w-3.5 h-3.5 mr-1.5 text-success" /> : <Save className="w-3.5 h-3.5 mr-1.5 text-gray-400" />}
            {isSaved ? "Configuración Guardada" : "Guardar Cambios"}
          </button>
        </div>
      </div>
    </div>
  );
}
