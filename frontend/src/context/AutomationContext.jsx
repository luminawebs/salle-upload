import React, { createContext, useState, useRef, useEffect } from 'react';

export const AutomationContext = createContext();

const API_BASE = import.meta.env.VITE_API_BASE || "";

export const AutomationProvider = ({ children }) => {
  const [settings, setSettings] = useState({
    HEADLESS_MODE: 'False',
    ENABLE_DOCX_PARSING: 'False',
    ENABLE_DOCX_SPLITTING_HTML: 'False',
    ENABLE_UNIDADES_INTRO_SPLIT: 'False',
    ENABLE_COURSE_FORMAT_CHANGE: 'True',
    ENABLE_COURSE_STRUCTURE_CREATION: 'False',
    ENABLE_DOCX_UPLOAD_HTML: 'False',
    ENABLE_GLOSARIO_UPLOAD: 'False',
    ENABLE_CUESTIONARIO_EXPORT: 'False',
    ENABLE_CUESTIONARIO_GRADE_UPDATE: 'False',
    ENABLE_UNIDADES_INTRO_UPLOAD: 'False',
    ENABLE_DOCX_RUBRICA_UPLOAD: 'False',
    ENABLE_SECTION_RENAME: 'False',
    ENABLE_SECTION_DESCRIPTION_UPDATE: 'False',
    ENABLE_GENERATE_HTML_INTRO: 'False',
    ENABLE_GENERATE_HTML_INTRO_GENERAL: 'False',
    ENABLE_INFOGRAFIA_EXPORT: 'False',
    ENABLE_FORO_EXPORT: 'False',
    ENABLE_ACTUALIDAD_EXPORT: 'False',
    ENABLE_PREGUNTAS_EXPORT: 'False',
    ENABLE_RECURSOS_APOYO_EXPORT: 'False',
    ENABLE_RECURSOS_APOYO_EDIT_CLASSES: 'False',
    ENABLE_ACTIVIDAD_EXPORT: 'False',
    ENABLE_ACTIVIDAD_RECURSOS_EXPORT: 'False',
    ENABLE_ACTIVIDAD_RUBRICA_EXPORT: 'False',
    ENABLE_TRABAJO_EXPORT: 'False',
    ENABLE_TRABAJO_RUBRICA_EXPORT: 'False',
    ENABLE_EVIDENCIA_EXPORT: 'False',
    ENABLE_EVIDENCIA_RUBRICA_EXPORT: 'False',
    ENABLE_RECURSOS_HTML_EXPORT: 'False',
    ENABLE_CLEAR_PUNTOS_EXTRAS: 'False',
    ENABLE_PUNTOS_EXTRAS_EXPORT: 'False',
    ENABLE_RECUPERACION_EXPORT: 'False',
    ENABLE_AJUSTE_COMPETENCIAS: 'False',
    ENABLE_CONFIGURACION_FINAL: 'False',
    ENABLE_MATERIALES_ESTUDIO_EXPORT: 'False',
    ENABLE_ACTIVITY_COMPLETION_UPDATE: 'True',
    ENABLE_FINAL_COURSE_FORMAT_BUTTONS: 'False',
    COURSES_TO_PROCESS: '9'
  });

  const [logs, setLogs] = useState([]);
  const [status, setStatus] = useState('Ready'); // Ready, Running, Completed, Failed
  const [progress, setProgress] = useState(0);
  const [currentTaskLabel, setCurrentTaskLabel] = useState('Esperando para iniciar...');
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [activeLogTab, setActiveLogTab] = useState(0);
  const [courseName, setCourseName] = useState('');
  const [isSaved, setIsSaved] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState({
    parsing: true,
    structure: true,
    resources: false,
    activities: false,
    rubrics: false,
    assessments: false,
    finalization: false
  });

  const toggleCategory = (id) => {
    setExpandedCategories(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  const currentLogPhase = useRef(0);
  const eventSourceRef = useRef(null);

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

  const handleSetSetting = (key, value) => {
    if (status === 'Running') return;
    setSettings(prev => ({ ...prev, [key]: value }));
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

  const handleRun = async (handleSaveSettings) => {
    if (handleSaveSettings) {
      await handleSaveSettings();
    }
    
    setStatus('Running');
    setProgress(5);
    setElapsedSeconds(0);
    setActiveLogTab(0);
    currentLogPhase.current = 0;
    setCurrentTaskLabel('Iniciando entorno Moodle...');
    setLogs([{ text: "[Sistema] Conectando con el proceso de automatización...", phase: 0, timeStr: new Date().toLocaleTimeString() }]);

    let localHasFailed = false;

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const eventSource = new EventSource(`${API_BASE}/api/logs`);
    eventSourceRef.current = eventSource;

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
        eventSource.close();
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
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <AutomationContext.Provider value={{
      settings, setSettings,
      handleToggle, handleSetSetting, handleSaveSettings, isSaved,
      logs, setLogs,
      status, setStatus,
      progress, setProgress,
      currentTaskLabel, setCurrentTaskLabel,
      elapsedSeconds, setElapsedSeconds,
      activeLogTab, setActiveLogTab,
      courseName, setCourseName,
      expandedCategories, toggleCategory,
      handleRun, handleStop
    }}>
      {children}
    </AutomationContext.Provider>
  );
};
