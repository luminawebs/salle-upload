import React, { useContext, useState } from 'react';
import { AutomationContext } from '../context/AutomationContext';
import { Settings, Save, Check, ChevronDown, ChevronRight, Play } from 'lucide-react';

const CATEGORIES = [
  {
    id: 'parsing',
    title: '1. Procesamiento de Documentos',
    flags: [
      { key: 'ENABLE_DOCX_PARSING', label: 'Extraer contenido de DOCX' },
      { key: 'ENABLE_DOCX_SPLITTING_HTML', label: 'Generar Fragmentos HTML de Actividades' },
      { key: 'ENABLE_UNIDADES_INTRO_SPLIT', label: 'Dividir Introducción de Unidades' }
    ]
  },
  {
    id: 'structure',
    title: '2. Estructura y Formato del Curso',
    flags: [
      { key: 'ENABLE_COURSE_FORMAT_CHANGE', label: 'Cambiar a formato Secciones (Temporal)' },
      { key: 'ENABLE_COURSE_STRUCTURE_CREATION', label: 'Crear Estructura de Secciones' },
      { key: 'ENABLE_SECTION_RENAME', label: 'Renombrar Secciones' },
      { key: 'ENABLE_SECTION_DESCRIPTION_UPDATE', label: 'Actualizar Descripciones de Sección' },
    ]
  },
  {
    id: 'resources',
    title: '3. Generación y Carga de Recursos',
    flags: [
      { key: 'ENABLE_GENERATE_HTML_INTRO', label: 'Generar Intro HTML (Local)' },
      { key: 'ENABLE_GENERATE_HTML_INTRO_GENERAL', label: 'Generar Intro General HTML' },
      { key: 'ENABLE_DOCX_UPLOAD_HTML', label: 'Subir Recursos HTML (Actividades)' },
      { key: 'ENABLE_UNIDADES_INTRO_UPLOAD', label: 'Subir Introducciones de Unidades' },
      { key: 'ENABLE_DOCX_RUBRICA_UPLOAD', label: 'Subir Rúbricas (Documentos)' },
      { key: 'ENABLE_RECURSOS_HTML_EXPORT', label: 'Exportar Recursos HTML Adicionales' }
    ]
  },
  {
    id: 'activities',
    title: '4. Configuración de Actividades',
    flags: [
      { key: 'ENABLE_FORO_EXPORT', label: 'Exportar Foros' },
      { key: 'ENABLE_ACTUALIDAD_EXPORT', label: 'Exportar Actividad de Actualidad' },
      { key: 'ENABLE_ACTIVIDAD_EXPORT', label: 'Exportar Tareas/Actividades (Local/Remote)' },
      { key: 'ENABLE_TRABAJO_EXPORT', label: 'Exportar Trabajo Final' },
      { key: 'ENABLE_EVIDENCIA_EXPORT', label: 'Exportar Evidencias' },
      { key: 'ENABLE_RECURSOS_APOYO_EXPORT', label: 'Exportar Recursos de Apoyo' },
      { key: 'ENABLE_RECURSOS_APOYO_EDIT_CLASSES', label: 'Editar Clases de Recursos de Apoyo' },
      { key: 'ENABLE_MATERIALES_ESTUDIO_EXPORT', label: 'Exportar Materiales de Estudio' }
    ]
  },
  {
    id: 'rubrics',
    title: '5. Rúbricas en Moodle',
    flags: [
      { key: 'ENABLE_ACTIVIDAD_RUBRICA_EXPORT', label: 'Exportar Rúbricas de Actividades' },
      { key: 'ENABLE_TRABAJO_RUBRICA_EXPORT', label: 'Exportar Rúbrica de Trabajo Final' },
      { key: 'ENABLE_EVIDENCIA_RUBRICA_EXPORT', label: 'Exportar Rúbrica de Evidencias' }
    ]
  },
  {
    id: 'assessments',
    title: '6. Evaluaciones y Cuestionarios',
    flags: [
      { key: 'ENABLE_PREGUNTAS_EXPORT', label: 'Exportar Banco de Preguntas' },
      { key: 'ENABLE_CUESTIONARIO_EXPORT', label: 'Crear Cuestionarios en Moodle' },
      { key: 'ENABLE_CUESTIONARIO_GRADE_UPDATE', label: 'Configurar Calificaciones (Cuestionarios)' },
      { key: 'ENABLE_CLEAR_PUNTOS_EXTRAS', label: 'Limpiar Puntos Extras Antiguos' },
      { key: 'ENABLE_PUNTOS_EXTRAS_EXPORT', label: 'Exportar Puntos Extras' },
      { key: 'ENABLE_RECUPERACION_EXPORT', label: 'Exportar Actividad de Recuperación' }
    ]
  },
  {
    id: 'finalization',
    title: '7. Ajustes Finales y Competencias',
    flags: [
      { key: 'ENABLE_AJUSTE_COMPETENCIAS', label: 'Ajuste de Competencias' },
      { key: 'ENABLE_CONFIGURACION_FINAL', label: 'Configuración Final (Limpieza/Estilos)' },
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
    <div className="flex flex-col h-full overflow-hidden bg-surface rounded-xl border border-border shadow-sm">
      
      {/* Header and Controls */}
      <div className="p-5 border-b border-border bg-background">
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
