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

// const API_BASE = "http://127.0.0.1:8000";
// const API_BASE = "http://157.230.50.37:8000";
// const API_BASE = window.location.origin;
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
      { key: 'ENABLE_DOCX_UPLOAD_HTML', label: 'Subir Recursos HTML' }
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

export default function MoodleEngineView({ setActiveTab }) {
  const {
    settings,
    logs, status, progress, currentTaskLabel,
    elapsedSeconds, activeLogTab, setActiveLogTab, courseName, setCourseName, setLogs,
    handleRun, handleStop
  } = useContext(AutomationContext);

  const [uploadedFile, setUploadedFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState('idle'); // idle, uploading, done, error
  const [isDragging, setIsDragging] = useState(false);

  const logsEndRef = useRef(null);

  const formatTime = (totalSeconds) => {
    const m = Math.floor(totalSeconds / 60);
    const s = totalSeconds % 60;
    return `${m}m ${s}s`;
  };

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

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
      await fetch(`${API_BASE}/api/upload`, {
        method: 'POST',
        body: formData
      });
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
    e.target.value = null; // Reset the input value so the same file can be re-uploaded
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

  return (
    <div className="h-screen bg-background text-gray-200 font-sans flex flex-col overflow-hidden">
      <header className="h-16 bg-surface border-b border-border flex items-center justify-between px-6 sticky top-0 z-10">
        <div className="flex items-center space-x-6">
          <img src="/logo.png" alt="La Salle" className="h-8 object-contain" />
          <div className="h-6 w-px bg-border"></div>
          <h1 className="text-lg font-bold tracking-tight text-white flex items-center">
            Moodle Automation Engine
            {/* <span className="ml-3 px-2 py-0.5 rounded text-xs font-semibold bg-primary/20 text-primary border border-primary/30">Producción</span> */}
          </h1>
          <div className="h-6 w-px bg-border ml-4 mr-2"></div>
          <NavigationTabs activeTab="moodle" setActiveTab={setActiveTab} />
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

        {/* Third Panel: Monitor (col-span-6) */}
        <div className="xl:col-span-6 flex flex-col space-y-6 min-h-0 h-full">



          {/* Terminal Console */}
          <div className="flex-1 flex flex-col min-h-0">
            <div className="flex bg-surface rounded-t-xl border border-border border-b-0 overflow-hidden">
              {WORKFLOW_PHASES.map((phase, idx) => (
                <button
                  key={phase.id}
                  onClick={() => setActiveLogTab(idx)}
                  className={`flex-1 py-2.5 px-1 text-[10px] sm:text-[11px] font-bold text-center uppercase tracking-tight transition-colors border-b-2 ${activeLogTab === idx ? 'bg-[#1e2638] text-primary border-primary' : 'bg-surface text-gray-500 border-transparent hover:text-gray-300 hover:bg-[#1e2638]/50'}`}
                >
                  <span className="truncate block w-full">{phase.shortTitle}</span>
                </button>
              ))}
            </div>

            <div className="flex-1 bg-[#0f141f] rounded-b-xl border border-border flex flex-col relative shadow-inner min-h-0">
              <div className="flex items-center px-4 py-2 border-b border-white/5 bg-black/20">
                <Terminal className="w-4 h-4 text-gray-400 mr-2" />
                <h2 className="text-xs font-semibold text-gray-300 uppercase tracking-widest">
                  Terminal de Moodle
                </h2>
                <div className="ml-auto flex items-center space-x-4">
                  <div className="flex space-x-1.5">
                    <div className="w-2.5 h-2.5 rounded-full bg-error/50"></div>
                    <div className="w-2.5 h-2.5 rounded-full bg-warning/50"></div>
                    <div className="w-2.5 h-2.5 rounded-full bg-success/50"></div>
                  </div>
                </div>
              </div>

              <div className="flex-1 p-4 overflow-y-auto font-mono text-[13px] leading-relaxed space-y-2" >
                {logs.filter(l => l.phase === activeLogTab).length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-gray-600">
                    <Activity className="w-8 h-8 mb-3 opacity-20" />
                    <p>Esperando datos para esta fase...</p>
                  </div>
                ) : (
                  logs.filter(l => l.phase === activeLogTab).map((logObj, i) => {
                    const log = logObj.text;
                    let color = 'text-gray-300';
                    let icon = null;

                    const lower = log.toLowerCase();
                    if (lower.includes("error") || lower.includes("fail") || lower.includes("exception")) {
                      color = 'text-error';
                      icon = <span className="text-error mr-2">✖</span>;
                    } else if (lower.includes("warning") || lower.includes("skip")) {
                      color = 'text-warning';
                      icon = <span className="text-warning mr-2">⚠</span>;
                    } else if (lower.includes("success") || lower.includes("éxito") || lower.includes("ok") || lower.includes("completad")) {
                      color = 'text-success';
                      icon = <span className="text-success mr-2">✓</span>;
                    } else if (lower.includes("sistema") || lower.includes("iniciando")) {
                      color = 'text-primary';
                      icon = <span className="text-primary mr-2">➜</span>;
                    } else {
                      icon = <span className="text-gray-600 mr-2">·</span>;
                    }

                    return (
                      <div key={i} className={`flex items-start ${color}`}>
                        <span className="text-gray-600 mr-3 shrink-0 text-xs mt-0.5">[{logObj.timeStr}]</span>
                        {icon}
                        <span className="break-all">{log}</span>
                      </div>
                    );
                  })
                )}
                <div ref={logsEndRef} />
              </div>
            </div>

            <div className="flex justify-end mt-4 shrink-0">
              <button
                onClick={handleDownloadLogs}
                className="flex items-center px-4 py-2 bg-[#1e2638] hover:bg-primary/90 text-white font-medium rounded-lg transition-colors shadow-sm text-sm border border-border hover:border-primary/50"
              >
                <Download className="w-4 h-4 mr-2" />
                Descargar todos los registros (.txt)
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

