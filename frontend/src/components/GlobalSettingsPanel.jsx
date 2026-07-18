import React, { useContext, useState } from 'react';
import { AutomationContext } from '../context/AutomationContext';
import { Settings, Save, Check, ChevronDown, ChevronRight, Play } from 'lucide-react';

const CATEGORIES = [
  {
    id: 'parsing',
    title: '1. Procesamiento de Documentos',
    flags: [
      { key: 'ENABLE_DOCX_PARSING', label: 'Extraer contenido de DOCX' },
      { key: 'ENABLE_DOCX_SPLITTING_HTML', label: 'Generar Fragmentos HTML' },
      { key: 'ENABLE_UNIDADES_INTRO_SPLIT', label: 'Dividir Introducción de Unidades' }
    ]
  },
  {
    id: 'structure',
    title: '2. Estructura en Moodle',
    flags: [
      { key: 'ENABLE_COURSE_FORMAT_CHANGE', label: 'Cambiar a formato Secciones (Temporal)' },
      { key: 'ENABLE_COURSE_STRUCTURE_CREATION', label: 'Crear Estructura de Secciones' },
      { key: 'ENABLE_UNIDADES_INTRO_UPLOAD', label: 'Subir Introducciones' },
      { key: 'ENABLE_DOCX_UPLOAD_HTML', label: 'Subir Recursos HTML (Actividades)' },
    ]
  },
  {
    id: 'assessments',
    title: '3. Evaluaciones y Cuestionarios',
    flags: [
      { key: 'ENABLE_DOCX_RUBRICA_UPLOAD', label: 'Subir Rúbricas' },
      { key: 'ENABLE_CUESTIONARIO_EXPORT', label: 'Crear Banco de Preguntas' },
      { key: 'ENABLE_CUESTIONARIO_GRADE_UPDATE', label: 'Configurar Calificaciones' }
    ]
  },
  {
    id: 'finalization',
    title: '4. Finalización',
    flags: [
      { key: 'ENABLE_ACTIVITY_COMPLETION_UPDATE', label: 'Actualizar Criterios de Finalización' },
      { key: 'ENABLE_FINAL_COURSE_FORMAT_BUTTONS', label: 'Cambiar a Formato Botones (Definitivo)' }
    ]
  }
];

export default function GlobalSettingsPanel() {
  const {
    settings,
    handleToggle,
    handleSetSetting,
    handleSaveSettings,
    isSaved,
    status,
    expandedCategories,
    toggleCategory,
    handleRun,
    handleStop
  } = useContext(AutomationContext);

  const handleSelectAllCategory = (e, categoryFlags, selectAll) => {
    e.stopPropagation();
    if (status === 'Running') return;
    categoryFlags.forEach(f => {
      handleSetSetting(f.key, selectAll ? 'True' : 'False');
    });
  };

  const isRunning = status === 'Running';

  return (
    <div className="flex flex-col overflow-hidden bg-surface rounded-xl border border-border shadow-sm">

      {/* Configuration List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-3">
        {CATEGORIES.map(category => {
          const isExpanded = expandedCategories[category.id];
          const activeCount = category.flags.filter(f => settings[f.key] === 'True').length;
          const allChecked = activeCount === category.flags.length;

          return (
            <div key={category.id} className="bg-background border border-border rounded-lg overflow-hidden transition-colors hover:border-gray-700">
              <div
                className="p-3 flex items-center justify-between cursor-pointer hover:bg-surface/30 select-none"
                onClick={() => toggleCategory(category.id)}
              >
                <div className="flex items-center space-x-2">
                  {isExpanded ? <ChevronDown className="w-4 h-4 text-primary" /> : <ChevronRight className="w-4 h-4 text-gray-500" />}
                  <h3 className="text-xs font-semibold text-white tracking-wide">{category.title}</h3>
                </div>
                <div className="flex items-center space-x-3">
                  <span className="text-[10px] text-gray-500 font-medium">{activeCount}/{category.flags.length}</span>
                </div>
              </div>

              {isExpanded && (
                <div className="px-3 pb-3 pt-1 border-t border-border/50 bg-background/50 space-y-1">
                  <div className="flex justify-end mb-2">
                    <button
                      onClick={(e) => handleSelectAllCategory(e, category.flags, !allChecked)}
                      disabled={isRunning}
                      className="text-[10px] px-2 py-1 rounded bg-surface border border-border hover:border-gray-500 text-gray-400 transition hover:text-white disabled:opacity-50"
                    >
                      {allChecked ? 'Deseleccionar Grupo' : 'Seleccionar Grupo'}
                    </button>
                  </div>

                  {category.flags.map(flag => {
                    const isActive = settings[flag.key] === 'True';
                    return (
                      <label
                        key={flag.key}
                        className={`flex items-center p-2 rounded-md cursor-pointer transition border ${isActive ? 'bg-primary/5 border-primary/20' : 'bg-transparent border-transparent hover:bg-surface/50'} ${isRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
                      >
                        <div className={`w-4 h-4 rounded-sm border flex items-center justify-center mr-2.5 shrink-0 transition-colors ${isActive ? 'bg-primary border-primary' : 'bg-surface border-gray-600'}`}>
                          {isActive && <Check className="w-3 h-3 text-white" />}
                        </div>
                        <span className={`text-[11px] leading-tight ${isActive ? 'text-gray-100 font-medium' : 'text-gray-400'}`}>
                          {flag.label}
                        </span>
                        <input
                          type="checkbox"
                          className="hidden"
                          checked={isActive}
                          onChange={() => handleToggle(flag.key)}
                          disabled={isRunning}
                        />
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

    </div>
  );
}
