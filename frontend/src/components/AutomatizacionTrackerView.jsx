import React, { useState, useEffect, useRef, useContext } from 'react';
import {
  Upload, Play, Save, Check, Terminal, Activity, FileText,
  FolderTree, BookOpen, Settings, CheckCircle2, Circle, Clock,
  AlertTriangle, XCircle, ChevronDown, ChevronUp, RefreshCw, Download
} from 'lucide-react';
import NavigationTabs from './NavigationTabs';
import GlobalSettingsPanel from './GlobalSettingsPanel';
import AutomationControls from './AutomationControls';
import { AutomationContext } from '../context/AutomationContext';

const API_BASE = import.meta.env.VITE_API_BASE || "";

const WORKFLOW_PHASES = [
  {
    id: 'doc_processing',
    title: 'Procesamiento de Documento',
    shortTitle: 'Procesamiento',
    icon: <FileText className="w-5 h-5" />,
    estimatedMins: 2,
    tasks: [
      { key: 'ENABLE_DOCX_PARSING', label: 'Extraer contenido de DOCX' },
      { key: 'ENABLE_DOCX_SPLITTING_HTML', label: 'Generar Fragmentos HTML' },
      { key: 'ENABLE_UNIDADES_INTRO_SPLIT', label: 'Dividir Introducción de Unidades' }
    ]
  },
  {
    id: 'moodle_structure',
    title: 'Estructura en Moodle',
    shortTitle: 'Estructura',
    icon: <FolderTree className="w-5 h-5" />,
    estimatedMins: 3,
    tasks: [
      { key: 'ENABLE_COURSE_FORMAT_CHANGE', label: 'Cambiar formato a Secciones personalizadas' },
      { key: 'ENABLE_COURSE_STRUCTURE_CREATION', label: 'Crear Estructura del Curso' },
      { key: 'ENABLE_UNIDADES_INTRO_UPLOAD', label: 'Subir Introducciones' },
      { key: 'ENABLE_DOCX_UPLOAD_HTML', label: 'Subir Recursos HTML' },
      { key: 'ENABLE_GLOSARIO_UPLOAD', label: 'Crear y Subir Glosario' }
    ]
  },
  {
    id: 'assessments',
    title: 'Evaluaciones y Cuestionarios',
    shortTitle: 'Evaluaciones',
    icon: <BookOpen className="w-5 h-5" />,
    estimatedMins: 4,
    tasks: [
      { key: 'ENABLE_DOCX_RUBRICA_UPLOAD', label: 'Subir Rúbricas' },
      { key: 'ENABLE_CUESTIONARIO_EXPORT', label: 'Crear Banco de Preguntas' },
      { key: 'ENABLE_CUESTIONARIO_GRADE_UPDATE', label: 'Configurar Calificaciones' }
    ]
  },
  {
    id: 'finalization',
    title: 'Finalización',
    shortTitle: 'Finalización',
    icon: <CheckCircle2 className="w-5 h-5" />,
    estimatedMins: 1,
    tasks: [
      { key: 'ENABLE_ACTIVITY_COMPLETION_UPDATE', label: 'Actualizar Criterios de Finalización' },
      { key: 'ENABLE_FINAL_COURSE_FORMAT_BUTTONS', label: 'Configuración final del formato de curso (Botones)' }
    ]
  }
];

const CircularProgress = ({ percentage }) => {
  const radius = 40;
  const stroke = 8;
  const normalizedRadius = radius - stroke * 2;
  const circumference = normalizedRadius * 2 * Math.PI;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  return (
    <div className="flex flex-col items-center justify-center relative">
      <svg height={radius * 2} width={radius * 2}>
        <circle
          stroke="#222a3bff"
          fill="transparent"
          strokeWidth={stroke}
          r={normalizedRadius}
          cx={radius}
          cy={radius}
        />
        <circle
          stroke="#00D68F"
          fill="transparent"
          strokeWidth={stroke}
          strokeDasharray={circumference + ' ' + circumference}
          style={{ strokeDashoffset, transition: 'stroke-dashoffset 0.5s ease 0s' }}
          strokeLinecap="round"
          r={normalizedRadius}
          cx={radius}
          cy={radius}
          transform={`rotate(-90 ${radius} ${radius})`}
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center inset-0">
        <span className="text-sm font-bold text-white">{percentage}%</span>
      </div>
    </div>
  );
};

export default function AutomatizacionTrackerView({ setActiveTab }) {
  const {
    settings,
    logs, status, progress, currentTaskLabel,
    elapsedSeconds, activeLogTab, courseName, setCourseName, setLogs,
    handleRun, handleStop
  } = useContext(AutomationContext);

  const [uploadedFile, setUploadedFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState('idle');
  const [isDragging, setIsDragging] = useState(false);
  const [dynamicPhases, setDynamicPhases] = useState([]);

  const handleDownloadLogs = () => {
    if (!logs || logs.length === 0) return;
    const logText = logs.map(l => `[${l.timeStr}] ${l.text}`).join('\n');
    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'terminal_logs.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const processFile = async (file) => {
    if (!file) return;
    if (!file.name.endsWith('.docx') && !file.name.endsWith('.doc')) {
      setLogs(prev => [...prev, `[Sistema] Error: El archivo debe ser .docx`]);
      return;
    }

    setUploadedFile({ name: file.name, size: (file.size / 1024 / 1024).toFixed(2) + ' MB' });
    setUploadStatus('uploading');

    const formData = new FormData();
    formData.append("file", file);
    formData.append("course_id", settings.COURSES_TO_PROCESS);

    try {
      const res = await fetch(`${API_BASE}/api/upload`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();

      if (data.report && data.report.unidades) {
        let newPhases = [];
        let actIndex = 1;
        for (const [uNum, uData] of Object.entries(data.report.unidades)) {
          if (uData.actividades) {
            for (const [actNum, actData] of Object.entries(uData.actividades)) {
              const tipo = actData.tipo;
              let tasks = [];
              if (tipo === 'Foro') {
                tasks = [
                  { key: 'ENABLE_FORO_EXPORT', label: 'Exportar Foro' },
                  { key: 'ENABLE_ACTIVITY_COMPLETION_UPDATE', label: 'Condiciones de Finalización' }
                ];
              } else if (tipo === 'Cuestionario') {
                tasks = [
                  { key: 'ENABLE_PREGUNTAS_EXPORT', label: 'Exportar Preguntas (Banco)' },
                  { key: 'ENABLE_CUESTIONARIO_EXPORT', label: 'Exportar Cuestionario (Estructura)' },
                  { key: 'ENABLE_ACTIVITY_COMPLETION_UPDATE', label: 'Condiciones de Finalización' }
                ];
              } else if (tipo === 'Tarea' || tipo === 'Otra') {
                tasks = [
                  { key: 'ENABLE_ACTIVIDAD_EXPORT', label: 'Exportar Actividad' },
                  { key: 'ENABLE_ACTIVIDAD_RECURSOS_EXPORT', label: 'Exportar Recursos' },
                  { key: 'ENABLE_ACTIVIDAD_RUBRICA_EXPORT', label: 'Exportar Rúbrica' },
                  { key: 'ENABLE_ACTIVITY_COMPLETION_UPDATE', label: 'Condiciones de Finalización' }
                ];
              } else {
                tasks = [
                  { key: 'ENABLE_ACTIVIDAD_EXPORT', label: 'Exportar Actividad (Básica)' }
                ];
              }

              newPhases.push({
                id: `dynamic_act_${actIndex}`,
                title: `Actividad ${actNum} - ${tipo} (Unidad ${uNum})`,
                shortTitle: `Actividad ${actNum}`,
                icon: <Activity className="w-5 h-5" />,
                estimatedMins: 3,
                tipo: tipo
              });
              actIndex++;
            }
          }
        }
        setDynamicPhases(newPhases);
      }

      setUploadStatus('done');
      setLogs(prev => [...prev, `[Sistema] Archivo ${file.name} subido correctamente.`]);
    } catch (err) {
      console.error(err);
      setUploadStatus('error');
      setLogs(prev => [...prev, `[Sistema] Error al subir ${file.name}.`]);
    }
  };

  const handleUpload = (e) => {
    processFile(e.target.files[0]);
    e.target.value = null;
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const formatTime = (totalSeconds) => {
    const m = Math.floor(totalSeconds / 60);
    const s = totalSeconds % 60;
    return `${m}m ${s}s`;
  };

  return (
    <div className="h-screen bg-background text-gray-200 font-sans flex flex-col overflow-hidden">
      {/* Header */}
      <header className="h-16 bg-surface border-b border-border flex items-center justify-between px-6 sticky top-0 z-10">
        <div className="flex items-center space-x-6">
          <img src="/logo.png" alt="La Salle" className="h-8 object-contain" />
          <div className="h-6 w-px bg-border"></div>
          <h1 className="text-lg font-bold tracking-tight text-white flex items-center">
            Moodle Automation Engine
            {/* <span className="ml-3 px-2 py-0.5 rounded text-xs font-semibold bg-primary/20 text-primary border border-primary/30">Producción</span> */}
          </h1>
          <div className="h-6 w-px bg-border ml-4 mr-2"></div>
          <NavigationTabs activeTab="tracker" setActiveTab={setActiveTab} />
        </div>
      </header>

      {/* Main Layout: 3 Columns */}
      <main className="flex-1 p-6 grid grid-cols-1 xl:grid-cols-12 gap-6 max-w-[1600px] mx-auto w-full min-h-0 h-full">

        {/* First Column */}
        <div className="xl:col-span-3 flex flex-col gap-6 h-full min-h-[600px]">
          {/* Top Panel: Source Document (Fixed height) */}
          <div className="bg-surface rounded-xl border border-border p-5 shadow-sm shrink-0">
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider mb-5 flex items-center">
              <span className="w-2 h-2 rounded-full bg-primary mr-2"></span>
              Documento Fuente
            </h2>

            <label
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`flex flex-col items-center justify-center w-full h-40 border-2 border-dashed rounded-xl cursor-pointer transition-all ${isDragging ? 'border-primary bg-primary/10' : uploadStatus === 'uploading' ? 'border-primary bg-primary/5' : uploadStatus === 'done' ? 'border-success bg-success/5' : 'border-border hover:border-gray-500 hover:bg-gray-800/30'}`}
            >
              <div className="flex flex-col items-center justify-center pt-5 pb-6 text-center px-4">
                {uploadStatus === 'done' ? (
                  <CheckCircle2 className="w-8 h-8 text-success mb-2" />
                ) : (
                  <Upload className={`w-8 h-8 mb-2 ${uploadStatus === 'uploading' ? 'text-primary animate-bounce' : 'text-gray-500'}`} />
                )}

                {uploadedFile ? (
                  <>
                    <p className="text-sm font-medium text-white truncate max-w-[200px]">{uploadedFile.name}</p>
                    <p className="text-xs text-gray-400 mt-1">{uploadedFile.size}</p>
                    <p className="text-xs text-primary mt-2 hover:underline">Reemplazar archivo</p>
                  </>
                ) : (
                  <>
                    <p className="mb-1 text-sm text-gray-300"><span className="font-semibold text-primary">Arrastra tu archivo</span> o haz clic</p>
                    <p className="text-xs text-gray-500">Solo documentos .docx</p>
                  </>
                )}
              </div>
              <input type="file" accept=".docx" className="hidden" onChange={handleUpload} />
            </label>
          </div>

          <AutomationControls />


          {/* Bottom Panel: Monitor de Ejecución */}
          <div className="bg-surface rounded-xl border border-border p-4 shadow-sm">
            <h2 className="text-xs font-semibold text-white uppercase tracking-wider mb-3 flex items-center">
              <span className="w-2 h-2 rounded-full bg-primary mr-2"></span>Monitor de Ejecución
            </h2>
            <div className="flex flex-col items-center justify-center mb-3 py-2">
              <h3 className={`text-lg font-bold mb-1 ${status === 'running' ? 'text-primary' : status === 'done' ? 'text-success' : 'text-gray-300'}`}>
                {status === 'running' ? 'En ejecución' : status === 'done' ? 'Finalizado' : 'Listo para ejecutar'}
              </h3>
              <p className="text-xs text-gray-400 mb-4 text-center">
                {status === 'running' ? 'Procesando tareas automáticas...' : status === 'done' ? 'Flujo completado exitosamente.' : 'Todo en orden. Presiona ejecutar para iniciar.'}
              </p>

              <CircularProgress percentage={progress} />

              <div className="mt-4 flex flex-col items-center">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Tiempo de ejecución</p>
                <p className="text-xl font-bold text-primary mt-0.5">{formatTime(elapsedSeconds)}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Second Column: Global Settings Panel */}
        <div className="xl:col-span-3 flex flex-col gap-6 h-full">
          <div className="flex-1 min-h-[400px]">
            <GlobalSettingsPanel />
          </div>
        </div>

        {/* Third Panel: Horizontal Tracker (col-span-6) */}
        <div className="xl:col-span-6 flex flex-col gap-6 overflow-y-auto pr-2 custom-scrollbar h-full">


          <div className="space-y-4">
            {[...WORKFLOW_PHASES.slice(0, 2), ...dynamicPhases, ...WORKFLOW_PHASES.slice(3, 4)].map((phase, idx, arr) => {
              let phaseStatus = 'Pendiente';
              let phaseStatusColor = 'text-gray-400';
              let phaseBorder = 'border-border';

              if (status === 'Completed') {
                phaseStatus = 'Completado';
                phaseStatusColor = 'text-success';
              } else if (status === 'Running') {
                if (activeLogTab === idx) {
                  phaseStatus = 'En progreso';
                  phaseStatusColor = 'text-blue-400';
                  phaseBorder = 'border-primary/50';
                } else if (activeLogTab > idx) {
                  phaseStatus = 'Completado';
                  phaseStatusColor = 'text-success';
                }
              }

              const colorTheme = {
                Foro: {
                  iconText: 'text-blue-400', iconBg: 'bg-blue-900/20', iconBorder: 'border-blue-800/40',
                  checkActive: 'bg-blue-600 border-blue-600', checkCompleted: 'bg-blue-500 border-blue-500',
                  checkRunning: 'bg-blue-400 border-blue-400 shadow-[0_0_15px_rgba(96,165,250,0.4)]',
                  progressBg: 'bg-blue-500/70', progressCompleted: 'bg-blue-500/60'
                },
                Cuestionario: {
                  iconText: 'text-orange-400', iconBg: 'bg-orange-900/20', iconBorder: 'border-orange-800/40',
                  checkActive: 'bg-orange-600 border-orange-600', checkCompleted: 'bg-orange-500 border-orange-500',
                  checkRunning: 'bg-orange-400 border-orange-400 shadow-[0_0_15px_rgba(251,146,60,0.4)]',
                  progressBg: 'bg-orange-500/70', progressCompleted: 'bg-orange-500/60'
                },
                Tarea: {
                  iconText: 'text-pink-400', iconBg: 'bg-pink-900/20', iconBorder: 'border-pink-800/40',
                  checkActive: 'bg-pink-600 border-pink-600', checkCompleted: 'bg-pink-500 border-pink-500',
                  checkRunning: 'bg-pink-400 border-pink-400 shadow-[0_0_15px_rgba(244,114,182,0.4)]',
                  progressBg: 'bg-pink-500/70', progressCompleted: 'bg-pink-500/60'
                },
                Otra: {
                  iconText: 'text-teal-400', iconBg: 'bg-teal-900/20', iconBorder: 'border-teal-800/40',
                  checkActive: 'bg-teal-600 border-teal-600', checkCompleted: 'bg-teal-500 border-teal-500',
                  checkRunning: 'bg-teal-400 border-teal-400 shadow-[0_0_15px_rgba(45,212,191,0.4)]',
                  progressBg: 'bg-teal-500/70', progressCompleted: 'bg-teal-500/60'
                },
                default: {
                  iconText: 'text-primary', iconBg: 'bg-background', iconBorder: 'border-border',
                  checkActive: 'bg-purple-700 border-purple-700', checkCompleted: 'bg-purple-600 border-purple-600',
                  checkRunning: 'bg-primary border-primary shadow-[0_0_15px_rgba(0,214,143,0.4)]',
                  progressBg: 'bg-primary/70', progressCompleted: 'bg-purple-600/60'
                }
              };

              const theme = phase.tipo && colorTheme[phase.tipo] ? colorTheme[phase.tipo] : colorTheme.default;

              return (
                <div key={phase.id} className={`bg-surface rounded-xl border ${phaseBorder} p-5 shadow-sm transition-all`}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-3">
                      <div className={`p-2 rounded-lg border ${theme.iconBg} ${theme.iconText} ${theme.iconBorder}`}>
                        {phase.icon}
                      </div>
                      <div>
                        <h3 className="text-base font-semibold text-white">{phase.title}</h3>
                        <div className="flex items-center text-xs text-gray-400 mt-0.5">
                          <Clock className="w-3 h-3 mr-1" /> Est. {phase.estimatedMins} min
                        </div>
                      </div>
                    </div>
                    <div className={`text-sm px-3 py-1 rounded-full bg-background border border-border flex items-center ${phaseStatusColor}`}>
                      {phaseStatus === 'Completado' && <CheckCircle2 className="w-4 h-4 mr-1.5" />}
                      {phaseStatus === 'En progreso' && <Activity className="w-4 h-4 mr-1.5 animate-pulse" />}
                      {phaseStatus === 'Pendiente' && <Circle className="w-4 h-4 mr-1.5" />}
                      {phaseStatus}
                    </div>
                  </div>

                  {/* Horizontal Timeline */}
                  <div className="relative pt-2 pb-6">
                    {/* Connecting Line background */}
                    <div className="absolute top-6 left-0 right-0 h-1 bg-background border-t border-b border-border rounded"></div>

                    {/* Progress Line */}
                    {status === 'Running' && (
                      <div className={`absolute top-6 left-0 h-1 ${theme.progressBg} transition-all duration-500 rounded`} style={{
                        width: activeLogTab > idx ? '100%' : (activeLogTab === idx ? '50%' : '0%')
                      }}></div>
                    )}
                    {(status === 'Completed' || (activeLogTab > idx && status === 'Running')) && (
                      <div className={`absolute top-6 left-0 right-0 h-1 ${theme.progressCompleted} rounded`}></div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex justify-end w-full mb-2">
            <button
              onClick={handleDownloadLogs}
              className="flex items-center px-4 py-2 bg-surface hover:bg-gray-800 text-white font-medium rounded-lg transition-colors shadow-sm text-sm border border-border"
            >
              <Download className="w-4 h-4 mr-2" />
              Descargar todos los registros (.txt)
            </button>
          </div>
        </div>

      </main>
    </div>
  );
}
