import React, { useContext } from 'react';
import { ArrowLeft, Save, Check, AlertTriangle } from 'lucide-react';
import GlobalSettingsPanel from './GlobalSettingsPanel';
import { AutomationContext } from '../context/AutomationContext';

// "Configuración avanzada": which pipeline steps a run executes. Moved off the
// main page so it's not in the way of the upload → review → run flow; the
// main page still shows a one-line summary of active steps next to Run.
export default function AdvancedSettingsPage({ onBack }) {
  const { handleSaveSettings, isSaved, status } = useContext(AutomationContext);
  const isRunning = status === 'Running';

  return (
    <div className="max-w-3xl mx-auto w-full space-y-5">
      <button
        type="button"
        onClick={onBack}
        className="flex items-center text-xs text-gray-400 hover:text-white"
      >
        <ArrowLeft className="w-3.5 h-3.5 mr-1.5" /> Volver a la carga del curso
      </button>

      <div>
        <h2 className="text-lg font-bold text-white">Configuración avanzada</h2>
        <p className="text-sm text-gray-400 mt-1">
          Elige qué pasos ejecuta la automatización en Moodle. Normalmente no hace falta cambiar
          nada: úsalo para repetir solo una parte del proceso o saltarte un paso.
        </p>
        <p className="text-xs text-gray-500 mt-2">
          Los cambios se guardan con «Guardar cambios» o automáticamente al iniciar la automatización.
        </p>
      </div>

      {isRunning && (
        <p className="flex items-start text-xs text-warning bg-warning/10 border border-warning/30 rounded-lg px-3 py-2">
          <AlertTriangle className="w-3.5 h-3.5 mr-1.5 mt-0.5 flex-shrink-0" />
          Hay una automatización en curso: los pasos no se pueden cambiar hasta que termine.
        </p>
      )}

      <GlobalSettingsPanel />

      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleSaveSettings}
          disabled={isRunning}
          className="flex items-center px-4 py-2 rounded-lg text-sm font-semibold bg-primary hover:bg-primary-hover text-white disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {isSaved ? <Check className="w-4 h-4 mr-2" /> : <Save className="w-4 h-4 mr-2" />}
          {isSaved ? 'Cambios guardados' : 'Guardar cambios'}
        </button>
      </div>
    </div>
  );
}
