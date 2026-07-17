import React, { useState, useEffect, useRef } from 'react';
import {
  Upload, Play, Save, Check, Terminal, Activity, FileText,
  FolderTree, BookOpen, Settings, CheckCircle2, Circle, Clock,
  AlertTriangle, XCircle, ChevronDown, ChevronUp, RefreshCw, Download
} from 'lucide-react';
import NavigationTabs from './NavigationTabs';

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

export default function AutomatizacionTrackerView({ setActiveTab }) {
  const [settings, setSettings] = useState({
    HEADLESS_MODE: 'False',
    ENABLE_DOCX_PARSING: 'False',
    ENABLE_DOCX_SPLITTING_HTML: 'False',
    ENABLE_UNIDADES_INTRO_SPLIT: 'False',
    ENABLE_COURSE_FORMAT_CHANGE: 'True',
    ENABLE_COURSE_STRUCTURE_CREATION: 'False',
    ENABLE_UNIDADES_INTRO_UPLOAD: 'False',
    ENABLE_DOCX_UPLOAD_HTML: 'False',
    ENABLE_DOCX_RUBRICA_UPLOAD: 'False',
    ENABLE_CUESTIONARIO_EXPORT: 'False',
    ENABLE_CUESTIONARIO_GRADE_UPDATE: 'False',
    ENABLE_ACTIVITY_COMPLETION_UPDATE: 'True',
    ENABLE_FINAL_COURSE_FORMAT_BUTTONS: 'False',
    COURSES_TO_PROCESS: '9'
  });

  const [courseName, setCourseName] = useState('');
  const [uploadedFile, setUploadedFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState('idle');
  const [isDragging, setIsDragging] = useState(false);

  const [logs, setLogs] = useState([]);
  const [status, setStatus] = useState('Ready'); // Ready, Running, Completed, Failed
  const [isSaved, setIsSaved] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentTaskLabel, setCurrentTaskLabel] = useState('Esperando para iniciar...');
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [activeLogTab, setActiveLogTab] = useState(0);

  const currentLogPhase = useRef(0);

  useEffect(() => {
    let interval = null;
    if (status === 'Running') {
      interval = setInterval(() => {
        setElapsedSeconds(prev => prev + 1);
      }, 1000);
    } else {
      clearInterval(interval);
    }
    return () => clearInterval(interval);
  }, [status]);

  const formatTime = (totalSeconds) => {
    const m = Math.floor(totalSeconds / 60);
    const s = totalSeconds % 60;
    return `${m}m ${s}s`;
  };

  useEffect(() => {
    fetch(`${API_BASE}/api/settings`)
      .then(res => res.json())
      .then(data => setSettings(prev => ({ ...prev, ...data })))
      .catch(err => console.error("Error fetching settings:", err));
  }, []);

  const handleToggle = (key) => {
    if (status === 'Running') return;
    setSettings(prev => ({
      ...prev,
      [key]: prev[key] === 'True' ? 'False' : 'True'
    }));
  };

  const handleSaveSettings = async () => {
    try {
      await fetch(`${API_BASE}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      setIsSaved(true);
      setTimeout(() => setIsSaved(false), 2000);
    } catch (err) {
      console.error(err);
    }
  };

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

  const handleRun = async () => {
    await handleSaveSettings();
    setStatus('Running');
    setProgress(5);
    setElapsedSeconds(0);
    setActiveLogTab(0);
    currentLogPhase.current = 0;
    setCurrentTaskLabel('Iniciando entorno Moodle...');
    setLogs([{ text: "[Sistema] Conectando con el proceso de automatización...", phase: 0, timeStr: new Date().toLocaleTimeString() }]);

    let localHasFailed = false;

    const eventSource = new EventSource(`${API_BASE}/api/logs`);
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const msg = data.message;
      const lower = msg.toLowerCase();

      if (lower.includes("error al iniciar el proceso") || (lower.includes("código de salida") && !lower.includes("código de salida 0"))) {
        localHasFailed = true;
        setStatus('Failed');
        setCurrentTaskLabel('La ejecución se ha detenido por un error.');
      }

      if (lower.includes("proceso detenido por el usuario")) {
        localHasFailed = true;
        setStatus('Failed');
      }

      let newPhase = currentLogPhase.current;

      if (!localHasFailed) {
        if (lower.includes("course structure") || lower.includes("section rename") || lower.includes("uploading") || lower.includes("subiendo recursos")) {
          newPhase = 1;
          setProgress(35);
          setCurrentTaskLabel("Estructurando Moodle");
        }
        if (lower.includes("cuestionario") || lower.includes("actividad") || lower.includes("foro") || lower.includes("quiz") || lower.includes("exporting questions")) {
          newPhase = 2;
          setProgress(65);
          setCurrentTaskLabel("Configurando Evaluaciones");
        }
        if (lower.includes("competencias") || lower.includes("configuracion final") || lower.includes("limpieza") || lower.includes("activity completion") || lower.includes("criterios de finalización")) {
          newPhase = 3;
          setProgress(90);
          setCurrentTaskLabel("Finalizando automatización");
        }

        currentLogPhase.current = newPhase;
        setActiveLogTab(newPhase);
      }

      const timeStr = new Date().toLocaleTimeString('es-ES', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
      setLogs(prev => [...prev, { text: msg, phase: newPhase, timeStr }]);

      const lowerMsg = msg.toLowerCase();
      if (lowerMsg.includes("nombre del curso:") || lowerMsg.includes("course name:")) {
        const parts = msg.split(/nombre del curso:|course name:/i);
        if (parts.length > 1) {
          setCourseName(parts[1].trim());
        }
      }

      if (msg.includes("La tarea finalizó") || msg.includes("Limpieza completada")) {
        if (!localHasFailed) {
          setStatus('Completed');
          setProgress(100);
          setCurrentTaskLabel('Flujo completado exitosamente.');
        }
      }
    };

    try {
      await fetch(`${API_BASE}/api/run`, { method: 'POST' });
    } catch (err) {
      console.error(err);
      setStatus('Failed');
    }
  };

  const handleStop = async () => {
    try {
      await fetch(`${API_BASE}/api/stop`, { method: 'POST' });
      setStatus('Failed');
      setCurrentTaskLabel('Tarea cancelada por el usuario.');
    } catch (err) {
      console.error(err);
    }
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
            <span className="ml-3 px-2 py-0.5 rounded text-xs font-semibold bg-primary/20 text-primary border border-primary/30">Producción</span>
          </h1>
          <div className="h-6 w-px bg-border ml-4 mr-2"></div>
          <NavigationTabs activeTab="tracker" setActiveTab={setActiveTab} />
        </div>
      </header>

      {/* Main Layout: 2 Columns */}
      <main className="flex-1 p-6 grid grid-cols-1 xl:grid-cols-12 gap-6 max-w-[1600px] mx-auto w-full min-h-0 h-full">

        {/* Left Panel: Inputs (col-span-3) */}
        <div className="xl:col-span-3 flex flex-col gap-6 overflow-y-auto pr-2 custom-scrollbar h-full">
          <div className="bg-surface rounded-xl border border-border p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider mb-5 flex items-center">
              <span className="w-2 h-2 rounded-full bg-primary mr-2"></span>
              Paso 1: Información
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">Moodle Course ID</label>
                <input
                  type="text"
                  value={settings.COURSES_TO_PROCESS}
                  onChange={(e) => setSettings({ ...settings, COURSES_TO_PROCESS: e.target.value })}
                  className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-white focus:ring-1 focus:ring-primary focus:border-primary outline-none transition"
                />
              </div>
              <div className="bg-background border border-border rounded-lg px-3 py-2 flex flex-col justify-center min-h-[42px]">
                <label className="block text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-0.5">Nombre del Curso Detectado</label>
                <span className="text-sm text-white font-medium truncate">
                  {status === 'Ready' ? 'Esperando inicio...' : courseName || 'Extrayendo del documento...'}
                </span>
              </div>
            </div>
          </div>

          <div className="bg-surface rounded-xl border border-border p-5 shadow-sm">
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

          <div className="bg-surface rounded-xl border border-border p-4 shadow-sm">
            <h2 className="text-xs font-semibold text-white uppercase tracking-wider mb-3 flex items-center">
              <span className="w-2 h-2 rounded-full bg-primary mr-2"></span>
              Monitor de Ejecución
            </h2>

            <div className="flex flex-col items-center justify-center mb-3 py-2">
              <h3 className="text-lg font-bold text-success mb-1">
                {status === 'Ready' && 'Listo para ejecutar'}
                {status === 'Running' && 'Ejecutando'}
                {status === 'Completed' && 'Completado'}
                {status === 'Failed' && 'Ejecución Incompleta'}
              </h3>
              <p className="text-xs text-gray-400 mb-4 text-center">
                {status === 'Ready' && 'Todo en orden. Presiona ejecutar para iniciar.'}
                {status === 'Running' && currentTaskLabel}
                {status === 'Completed' && 'El proceso ha finalizado exitosamente.'}
                {status === 'Failed' && 'La ejecución se ha detenido por un error.'}
              </p>
              <CircularProgress percentage={progress} />

              <div className="mt-4 flex flex-col items-center">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Tiempo de ejecución</p>
                <p className="text-xl font-bold text-primary mt-0.5">{formatTime(elapsedSeconds)}</p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-1 items-center">
            <div className="flex space-x-3 mt-6">
              <button
                onClick={handleRun}
                disabled={status === 'Running'}
                className={`flex-1 py-3 px-4 rounded-lg font-semibold flex items-center justify-center transition-all ${status === 'Running'
                  ? 'bg-primary/50 text-white cursor-not-allowed'
                  : 'bg-primary hover:bg-primary-hover text-white shadow-lg shadow-primary/20 hover:shadow-primary/40 hover:-translate-y-0.5'
                  }`}
              >
                <svg className={`w-5 h-5 mr-2 ${status === 'Running' ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  {status === 'Running' ? (
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  ) : (
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  )}
                </svg>
                {status === 'Running' ? "Procesando..." : "Iniciar Automatización"}
              </button>
              {status === 'Running' && (
                <button
                  onClick={handleStop}
                  className="py-3 px-6 rounded-lg font-semibold flex items-center justify-center transition-all bg-red-600 hover:bg-red-500 text-white shadow-lg shadow-red-600/20 hover:shadow-red-500/40 hover:-translate-y-0.5"
                >
                  <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
                  </svg>
                  Detener
                </button>
              )}
            </div>
            <button
              onClick={handleSaveSettings}
              className="flex items-center  py-4 hover:bg-gray-800 rounded-lg transition text-sm justify-center w-full font-medium border border-transparent hover:border-border"
            >
              {isSaved ? <Check className="w-4 h-4 mr-2 text-success" /> : <Save className="w-4 h-4 mr-2 text-gray-400" />}
              {isSaved ? "Guardado" : "Guardar Configuración"}
            </button>
          </div>
        </div>

        {/* Right Panel: Horizontal Tracker (col-span-9) */}
        <div className="xl:col-span-9 flex flex-col gap-6 overflow-y-auto pr-2 custom-scrollbar h-full">
          <div className="flex justify-end w-full mb-2">
            <button
                onClick={handleDownloadLogs}
                className="flex items-center px-4 py-2 bg-surface hover:bg-gray-800 text-white font-medium rounded-lg transition-colors shadow-sm text-sm border border-border"
              >
                <Download className="w-4 h-4 mr-2" />
                Descargar todos los registros (.txt)
            </button>
          </div>

          <div className="space-y-4">
            {WORKFLOW_PHASES.map((phase, idx) => {
              const activeCount = phase.tasks.filter(t => settings[t.key] === 'True').length;
              const allChecked = activeCount === phase.tasks.length;
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

              return (
                <div key={phase.id} className={`bg-surface rounded-xl border ${phaseBorder} p-5 shadow-sm transition-all`}>
                  <div className="flex items-center justify-between mb-8">
                    <div className="flex items-center space-x-3">
                      <div className="p-2 bg-background rounded-lg text-primary border border-border">
                        {phase.icon}
                      </div>
                      <div>
                        <h3 className="text-base font-semibold text-white">{phase.title}</h3>
                        <div className="flex items-center text-xs text-gray-400 mt-0.5">
                          <Clock className="w-3 h-3 mr-1" /> Est. {phase.estimatedMins} min
                          <span className="mx-2">•</span>
                          {activeCount} de {phase.tasks.length} activas
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
                        <div className="absolute top-6 left-0 h-1 bg-primary/70 transition-all duration-500 rounded" style={{
                            width: activeLogTab > idx ? '100%' : (activeLogTab === idx ? '50%' : '0%')
                        }}></div>
                    )}
                    {(status === 'Completed' || (activeLogTab > idx && status === 'Running')) && (
                        <div className="absolute top-6 left-0 right-0 h-1 bg-purple-600/60 rounded"></div>
                    )}

                    <div className="relative flex justify-between">
                      {phase.tasks.map((task, taskIdx) => {
                        const isActive = settings[task.key] === 'True';
                        
                        // Determine step status during execution
                        let stepState = 'pending'; // pending, active, completed
                        if (status === 'Completed') stepState = 'completed';
                        else if (status === 'Running') {
                            if (activeLogTab > idx) stepState = 'completed';
                            else if (activeLogTab === idx) {
                                // Simple approximation for UI: 
                                // Since we don't have granular task status, we'll mark all as in-progress if the phase is in progress.
                                stepState = 'active'; 
                            }
                        }

                        return (
                          <div key={task.key} className="flex flex-col items-center relative z-10 flex-1 px-2">
                            <button
                              onClick={() => handleToggle(task.key)}
                              disabled={status === 'Running'}
                              className={`w-8 h-8 rounded-full flex items-center justify-center transition-all border-2 flex-shrink-0
                                ${!isActive ? 'bg-background border-gray-600 text-gray-500 hover:border-gray-400' : 
                                  (stepState === 'completed' ? 'bg-purple-600 border-purple-600 text-white' : 
                                  (stepState === 'active' ? 'bg-primary border-primary text-white shadow-[0_0_15px_rgba(0,214,143,0.4)]' : 
                                  'bg-purple-700 border-purple-700 text-white shadow-lg'))}
                              `}
                            >
                              {isActive ? <Check className="w-4 h-4" /> : <div className="w-3 h-3 rounded-full bg-transparent border-2 border-gray-600" />}
                            </button>
                            <div className="mt-4 text-center">
                              <span className={`text-xs font-medium cursor-pointer hover:text-white transition-colors block
                                ${isActive ? 'text-gray-200' : 'text-gray-500'}
                              `} onClick={() => handleToggle(task.key)}>
                                {task.label}
                              </span>
                              {stepState === 'completed' && isActive && <span className="text-[10px] text-gray-400 mt-1 block">Completado</span>}
                              {stepState === 'active' && isActive && <span className="text-[10px] text-primary mt-1 block animate-pulse">En progreso</span>}
                              {(!isActive) && <span className="text-[10px] text-gray-600 mt-1 block">Ignorado</span>}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

      </main>
    </div>
  );
}
