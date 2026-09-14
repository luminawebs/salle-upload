import React, { createContext, useState, useRef, useEffect } from 'react';

export const AutomationContext = createContext();

const API_BASE = import.meta.env.VITE_API_BASE || "";

export const AutomationProvider = ({ children }) => {
  const [settings, setSettings] = useState({
    HEADLESS_MODE: 'False',
    ENABLE_COURSE_FORMAT_CHANGE: 'True',
    // The nine flags below default to True in config/settings.py — they
    // must match here. AutomationContext's state is the initial UI state
    // before /api/settings resolves, but it's also exactly what gets
    // POSTed back on "Guardar Cambios". If a value here disagreed with the
    // real backend default and .env didn't yet have that key set
    // explicitly, saving anything (even an unrelated field) would silently
    // write the wrong value into .env and disable that step from then on.
    ENABLE_COURSE_STRUCTURE_CREATION: 'True',
    ENABLE_DOCX_UPLOAD_HTML: 'True',
    ENABLE_GLOSARIO_UPLOAD: 'True',
    ENABLE_CUESTIONARIO_EXPORT: 'True',
    ENABLE_CUESTIONARIO_GRADE_UPDATE: 'True',
    ENABLE_UNIDADES_INTRO_UPLOAD: 'True',
    ENABLE_DOCX_RUBRICA_UPLOAD: 'True',
    ENABLE_MATERIALES_ESTUDIO_EXPORT: 'True',
    ENABLE_FINAL_COURSE_FORMAT_BUTTONS: 'True',
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
    ENABLE_ACTIVITY_COMPLETION_UPDATE: 'True',
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
  // Course ID that the currently-loaded parsed report actually belongs to
  // (i.e. the ID that was set at the moment a .docx was last uploaded/parsed
  // successfully). Used to warn/block "Run" if the ID field has since changed
  // and no longer matches what was actually analyzed.
  const [uploadedCourseId, setUploadedCourseId] = useState(null);
  const [expandedCategories, setExpandedCategories] = useState({
    parsing: true,
    structure: true,
    resources: false,
    activities: false,
    rubrics: false,
    assessments: false,
    finalization: false
  });

  const [popupMessage, setPopupMessage] = useState(null);

  const toggleCategory = (id) => {
    setExpandedCategories(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  const currentLogPhase = useRef(0);
  const runStartTimeRef = useRef(null);
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
      // Anchor to a real timestamp rather than counting ticks. setInterval
      // ticks aren't guaranteed to land exactly 1s apart — browsers throttle
      // timers in background/inactive tabs — so a "+1 per tick" counter
      // permanently falls behind real elapsed time once a tick is delayed.
      // Recomputing from Date.now() each tick means a late tick just catches
      // straight back up to the correct value instead of drifting forever.
      if (runStartTimeRef.current === null) {
        runStartTimeRef.current = Date.now();
      }
      const tick = () => {
        setElapsedSeconds(Math.floor((Date.now() - runStartTimeRef.current) / 1000));
      };
      tick();
      interval = setInterval(tick, 1000);
    } else {
      runStartTimeRef.current = null;
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

      // Check for specific errors that should trigger a popup
      if (lowerMsg.includes("could not find any edit mode toggle") || lowerMsg.includes("interruptor de modo de edición")) {
        setPopupMessage("No se encontró ningún botón o interruptor de modo de edición. Es posible que el usuario no tenga permisos de edición para este curso.");
      }
      if (lowerMsg.includes("no se encontró el documento en formato docx") || lowerMsg.includes("vuelva a subir el documento")) {
        setPopupMessage(msg); // Use the original message as it contains the course ID
      }
      if (lowerMsg.includes("not a valid course view page") || lowerMsg.includes("could not load course")) {
        setPopupMessage("No se pudo cargar el curso. Esto generalmente ocurre cuando el correo electrónico utilizado no está vinculado al curso.");
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
      uploadedCourseId, setUploadedCourseId,
      expandedCategories, toggleCategory,
      popupMessage, setPopupMessage,
      handleRun, handleStop
    }}>
      {children}
    </AutomationContext.Provider>
  );
};
