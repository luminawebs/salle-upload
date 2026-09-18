import React, { useContext, useState, useEffect, useRef } from 'react';
import {
  Upload, CheckCircle2, FileText, AlertTriangle, RefreshCw, XCircle,
  Code2, Eye, X, BookOpen, Terminal, Activity, Clock, Download
} from 'lucide-react';
import GlobalSettingsPanel from './GlobalSettingsPanel';
import AutomationControls from './AutomationControls';
import { AutomationContext } from '../context/AutomationContext';

const API_BASE = import.meta.env.VITE_API_BASE || "";

const WORKFLOW_PHASES = [
  { id: 'doc_processing', shortTitle: 'Procesamiento' },
  { id: 'moodle_structure', shortTitle: 'Estructura' },
  { id: 'assessments', shortTitle: 'Evaluaciones' },
  { id: 'finalization', shortTitle: 'Finalización' }
];

// How each report item maps to the fragment file the DOCX splitter actually
// wrote to disk. Best-effort: if the splitter had to disambiguate duplicate
// activity numbers (actividad3_1.html, etc.) the direct guess below can miss —
// the viewer just reports "fragmento no encontrado" in that case.
const fragmentTargetFor = (kind, params) => {
  if (kind === 'introduccion') return { category: 'introduccion', filename: 'introduccion_general.html' };
  if (kind === 'glosario') return { category: 'glosario', filename: 'glosario_import.xml' };
  if (kind === 'actividad') return { category: 'actividades', filename: `actividad${params.num}.html` };
  if (kind === 'material') return { category: 'material', filename: `Material_de_referencia_U${params.unit}.html` };
  return null;
};

function FragmentViewer({ target, title, courseId, onClose }) {
  const [content, setContent] = useState(null);
  const [status, setStatus] = useState('loading'); // loading, done, error
  const [errorMsg, setErrorMsg] = useState('');
  const [viewMode, setViewMode] = useState('preview'); // preview, source

  const isXml = target.filename.endsWith('.xml');

  useEffect(() => {
    let cancelled = false;
    setStatus('loading');
    const params = new URLSearchParams({
      course_id: courseId,
      category: target.category,
      filename: target.filename
    });
    fetch(`${API_BASE}/api/parsed-fragment?${params}`)
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'No se pudo cargar el fragmento.');
        return data;
      })
      .then((data) => {
        if (cancelled) return;
        setContent(data.content);
        setStatus('done');
        if (isXml) setViewMode('source');
      })
      .catch((err) => {
        if (cancelled) return;
        setErrorMsg(err.message);
        setStatus('error');
      });
    return () => { cancelled = true; };
  }, [target.category, target.filename, courseId]);

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-surface border border-border rounded-xl shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
          <div>
            <h3 className="text-sm font-bold text-white">{title}</h3>
            <p className="text-xs text-gray-500 mt-0.5">workspace/{courseId}/{target.category}/{target.filename}</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-800 text-gray-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {status === 'done' && !isXml && (
          <div className="flex items-center gap-2 px-5 pt-3 shrink-0">
            <button
              onClick={() => setViewMode('preview')}
              className={`flex items-center text-xs px-3 py-1.5 rounded-lg border ${viewMode === 'preview' ? 'bg-primary/20 border-primary/40 text-primary' : 'border-border text-gray-400 hover:text-white'}`}
            >
              <Eye className="w-3.5 h-3.5 mr-1.5" /> Vista previa
            </button>
            <button
              onClick={() => setViewMode('source')}
              className={`flex items-center text-xs px-3 py-1.5 rounded-lg border ${viewMode === 'source' ? 'bg-primary/20 border-primary/40 text-primary' : 'border-border text-gray-400 hover:text-white'}`}
            >
              <Code2 className="w-3.5 h-3.5 mr-1.5" /> HTML fuente
            </button>
          </div>
        )}

        <div className="p-5 overflow-y-auto custom-scrollbar flex-1">
          {status === 'loading' && (
            <div className="flex flex-col items-center justify-center py-10 text-gray-400">
              <RefreshCw className="w-6 h-6 animate-spin mb-2" />
              <p className="text-sm">Cargando fragmento parseado...</p>
            </div>
          )}

          {status === 'error' && (
            <div className="p-3 rounded-lg bg-error/10 border border-error/30 flex items-start text-error text-sm">
              <AlertTriangle className="w-5 h-5 mr-2 flex-shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {status === 'done' && viewMode === 'preview' && (
            <div
              className="prose prose-invert prose-sm max-w-none bg-background rounded-lg border border-border p-4"
              dangerouslySetInnerHTML={{ __html: content }}
            />
          )}

          {status === 'done' && viewMode === 'source' && (
            <pre className="text-xs text-gray-300 bg-background rounded-lg border border-border p-4 overflow-x-auto whitespace-pre-wrap break-words">
              {content}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

// A document the pipeline can't work with doesn't make it fail — it makes
// every step after parsing quietly find nothing to do, and the run then still
// looks like it succeeded. Catching that here, before Run, is far cheaper than
// after Moodle has been half-configured. Returns a message, or null if fine.
function describeDocumentProblem(report) {
  if (!report) {
    return 'No se pudo analizar el documento: el servidor no devolvió un reporte.';
  }
  const units = Object.values(report.unidades || {});
  if (units.length === 0) {
    return 'No se detectó ninguna Unidad en el documento (se reconocen los encabezados "UNIDAD DIDÁCTICA N" y "UNIDAD N." en su propia fila).';
  }
  const activityCount = units.reduce((n, u) => n + Object.keys(u.actividades || {}).length, 0);
  if (activityCount === 0) {
    return 'Se detectaron unidades, pero ninguna actividad.';
  }
  return null;
}

export default function AutomationView() {
  const {
    settings,
    status: runStatus, uploadedCourseId, setUploadedCourseId,
    setDocumentProblem, setDocumentProblemOverride, runSummary,
    logs, progress, activeLogTab, elapsedSeconds
  } = useContext(AutomationContext);

  const [uploadStatus, setUploadStatus] = useState('idle'); // idle, loading, done, error
  const [errorMsg, setErrorMsg] = useState('');
  const [report, setReport] = useState(null);
  const [fileInfo, setFileInfo] = useState(null); // { name, size }
  const [isDragging, setIsDragging] = useState(false);
  const [fragment, setFragment] = useState(null); // { target, title }
  const [viewMode, setViewMode] = useState('document'); // 'document' | 'terminal'
  const [skipped, setSkipped] = useState(new Set());

  const courseId = (settings.COURSES_TO_PROCESS || '').trim();
  const logsEndRef = useRef(null);

  useEffect(() => {
    if (viewMode === 'terminal') {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, viewMode]);

  const loadSkipped = async (cid) => {
    try {
      const res = await fetch(`${API_BASE}/api/skip-activities?course_id=${encodeURIComponent(cid)}`);
      const data = await res.json();
      setSkipped(new Set(data.skipped || []));
    } catch (err) {
      console.error('No se pudo cargar la lista de actividades excluidas:', err);
    }
  };

  const toggleSkip = async (actNum) => {
    const next = new Set(skipped);
    if (next.has(actNum)) next.delete(actNum); else next.add(actNum);
    setSkipped(next); // optimistic — this is a low-stakes, immediately-persisted toggle
    try {
      await fetch(`${API_BASE}/api/skip-activities`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ course_id: courseId, skipped: Array.from(next) })
      });
    } catch (err) {
      console.error('No se pudo guardar la exclusión de actividad:', err);
    }
  };

  const processFile = async (selectedFile) => {
    if (!selectedFile.name.endsWith('.docx')) {
      setErrorMsg('Por favor sube un archivo .docx válido.');
      setUploadStatus('error');
      return;
    }
    if (!courseId) {
      setErrorMsg('Escribe primero un ID de Curso.');
      setUploadStatus('error');
      return;
    }

    setUploadStatus('loading');
    setErrorMsg('');
    setReport(null);
    setUploadedCourseId(null);
    setDocumentProblem(null);
    setDocumentProblemOverride(false);
    setSkipped(new Set());

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("course_id", courseId);

    try {
      const response = await fetch(`${API_BASE}/api/upload`, { method: 'POST', body: formData });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Error procesando el documento');

      setReport(data.report || null);
      setDocumentProblem(describeDocumentProblem(data.report || null));
      setFileInfo({ name: selectedFile.name, size: (selectedFile.size / 1024 / 1024).toFixed(2) + ' MB' });
      setUploadedCourseId(courseId);
      setUploadStatus('done');
      loadSkipped(courseId);
    } catch (err) {
      console.error(err);
      setErrorMsg(err.message);
      setUploadStatus('error');
    }
  };

  // "Subir otro archivo diferente": drops back to the original upload
  // screen. A soft reset (not a full page reload) so in-progress global
  // settings aren't discarded along with it.
  const resetToUpload = () => {
    setUploadStatus('idle');
    setReport(null);
    setErrorMsg('');
    setFileInfo(null);
    setSkipped(new Set());
    setUploadedCourseId(null);
    setDocumentProblem(null);
    setDocumentProblemOverride(false);
    setFragment(null);
    setViewMode('document');
  };

  const handleDragOver = (e) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e) => { e.preventDefault(); setIsDragging(false); };
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files?.length > 0) processFile(e.dataTransfer.files[0]);
  };
  const handleUpload = (e) => {
    if (e.target.files?.length > 0) processFile(e.target.files[0]);
    e.target.value = null;
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

  const formatTime = (totalSeconds) => {
    const m = Math.floor(totalSeconds / 60);
    const s = totalSeconds % 60;
    return `${m}m ${s}s`;
  };

  const renderItem = (title, success, desc, onClickTarget) => {
    const body = (
      <div className="flex items-start p-3 border-t border-border mt-3">
        <div className={`mt-0.5 mr-3 flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center ${success ? 'bg-success/20 text-success' : 'bg-error/20 text-error'}`}>
          {success ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
        </div>
        <div className="flex-1">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-white">{title}</h4>
            {onClickTarget && success && (
              <span className="flex items-center text-[10px] text-primary">
                <Eye className="w-3 h-3 mr-1" /> Ver parseo
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400 mt-1">{desc}</p>
        </div>
      </div>
    );
    if (onClickTarget && success) {
      return (
        <button type="button" onClick={() => setFragment(onClickTarget)} className="text-left w-full hover:bg-primary/5 transition-colors">
          {body}
        </button>
      );
    }
    return body;
  };

  return (
    <div className="h-screen bg-background text-gray-200 font-sans flex flex-col overflow-hidden">
      <header className="h-16 bg-surface border-b border-border flex items-center px-6 sticky top-0 z-10 shrink-0">
        <img src="/logo.png" alt="La Salle" className="h-8 object-contain" />
        <div className="h-6 w-px bg-border mx-6"></div>
        <h1 className="text-lg font-bold tracking-tight text-white">Moodle Automation Engine</h1>
      </header>

      <main className="flex-1 p-6 grid grid-cols-1 xl:grid-cols-12 gap-6 max-w-[1600px] mx-auto w-full min-h-0 overflow-y-auto xl:overflow-hidden">

        {/* Column 1: Source document + run controls + progress */}
        <div className="xl:col-span-3 flex flex-col gap-6 h-full min-h-[600px]">
          <div className="bg-surface rounded-xl border border-border p-5 shadow-sm shrink-0">
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider mb-5 flex items-center">
              <span className="w-2 h-2 rounded-full bg-primary mr-2"></span>
              Documento Fuente
            </h2>

            {uploadStatus === 'done' && fileInfo ? (
              <div className="w-full border-2 border-success/40 bg-success/5 rounded-xl p-4 flex flex-col items-center text-center">
                <CheckCircle2 className="w-8 h-8 text-success mb-2" />
                <p className="text-sm font-medium text-white truncate max-w-full">{fileInfo.name}</p>
                <p className="text-xs text-gray-400 mt-1">{fileInfo.size}</p>
                <button
                  type="button"
                  onClick={resetToUpload}
                  className="mt-3 text-xs px-3 py-1.5 rounded-lg border border-border text-gray-300 hover:text-white hover:border-gray-500 transition-colors"
                >
                  Subir otro archivo diferente
                </button>
              </div>
            ) : (
              <label
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`flex flex-col items-center justify-center w-full h-40 border-2 border-dashed rounded-xl cursor-pointer transition-all ${isDragging ? 'border-primary bg-primary/10' : uploadStatus === 'loading' ? 'border-primary/50 bg-primary/5' : 'border-border hover:border-gray-500 hover:bg-surface/80'}`}
              >
                {uploadStatus === 'loading' ? (
                  <div className="flex flex-col items-center">
                    <RefreshCw className="w-8 h-8 text-primary animate-spin mb-2" />
                    <p className="text-sm font-medium text-white">Analizando documento...</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center text-center px-4">
                    <Upload className="w-8 h-8 mb-2 text-gray-400" />
                    <p className="mb-1 text-sm text-gray-200"><span className="font-semibold text-primary">Arrastra tu archivo</span> o haz clic</p>
                    <p className="text-xs text-gray-500">Solo documentos .docx</p>
                  </div>
                )}
                <input type="file" accept=".docx" className="hidden" onChange={handleUpload} disabled={uploadStatus === 'loading'} />
              </label>
            )}

            {uploadStatus === 'error' && (
              <div className="mt-4 p-3 rounded-lg bg-error/10 border border-error/30 flex items-start text-error text-sm">
                <AlertTriangle className="w-5 h-5 mr-2 flex-shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}
          </div>

          <AutomationControls onBeforeRun={() => setViewMode('terminal')} />

          <div className="bg-surface rounded-xl border border-border p-4 shadow-sm">
            <h2 className="text-xs font-semibold text-white uppercase tracking-wider mb-3 flex items-center">
              <span className="w-2 h-2 rounded-full bg-primary mr-2"></span>Monitor de Ejecución
            </h2>
            <div className="flex flex-col items-center justify-center py-2">
              <h3 className={`text-lg font-bold mb-1 ${
                runStatus === 'Running' ? 'text-primary'
                : runStatus === 'Completed' ? 'text-success'
                : runStatus === 'CompletedWithIssues' ? 'text-warning'
                : runStatus === 'Failed' ? 'text-error'
                : 'text-gray-300'}`}>
                {runStatus === 'Running' ? `En ejecución (${progress}%)`
                  : runStatus === 'Completed' ? 'Finalizado'
                  : runStatus === 'CompletedWithIssues' ? 'Finalizado con problemas'
                  : runStatus === 'Failed' ? 'Ejecución detenida'
                  : 'Listo para ejecutar'}
              </h3>
              <p className="text-xs text-gray-400 text-center">Tiempo: {formatTime(elapsedSeconds)}</p>
            </div>
            {runStatus === 'CompletedWithIssues' && runSummary.length > 0 && (
              <div className="mt-2 text-[11px] text-warning bg-warning/10 border border-warning/30 rounded-lg px-3 py-2 max-h-48 overflow-y-auto custom-scrollbar space-y-1">
                <p className="font-semibold">El proceso terminó, pero no todo se completó:</p>
                {runSummary.map((line, i) => (
                  <p key={i} className="break-words leading-snug">{line}</p>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Column 2: Global settings */}
        <div className="xl:col-span-3 flex flex-col gap-6 h-full">
          <div className="flex-1 min-h-[400px]">
            <GlobalSettingsPanel />
          </div>
        </div>

        {/* Column 3: Documento parseado <-> Terminal */}
        <div className="xl:col-span-6 flex flex-col gap-4 h-full min-h-0">
          <div className="flex items-center justify-between shrink-0">
            <div className="flex bg-surface rounded-xl border border-border p-1 w-fit">
              <button
                onClick={() => setViewMode('document')}
                className={`flex items-center px-4 py-1.5 text-xs font-semibold rounded-lg transition-all ${viewMode === 'document' ? 'bg-primary text-white shadow' : 'text-gray-400 hover:text-white'}`}
              >
                <FileText className="w-3.5 h-3.5 mr-1.5" /> Documento
              </button>
              <button
                onClick={() => setViewMode('terminal')}
                className={`flex items-center px-4 py-1.5 text-xs font-semibold rounded-lg transition-all ${viewMode === 'terminal' ? 'bg-primary text-white shadow' : 'text-gray-400 hover:text-white'}`}
              >
                <Terminal className="w-3.5 h-3.5 mr-1.5" /> Terminal
                {runStatus === 'Running' && <span className="ml-1.5 w-1.5 h-1.5 rounded-full bg-success animate-pulse" />}
              </button>
            </div>

            <button
              onClick={handleDownloadLogs}
              disabled={!logs || logs.length === 0}
              className="flex items-center px-3 py-1.5 bg-surface hover:bg-[#1e2638] text-gray-300 hover:text-white font-medium rounded-lg transition-colors shadow-sm text-xs border border-border hover:border-primary/50 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-surface disabled:hover:text-gray-300"
            >
              <Download className="w-3.5 h-3.5 mr-1.5" />
              Descargar todos los registros (.txt)
            </button>
          </div>

          {viewMode === 'document' ? (
            <div className="flex-1 overflow-y-auto custom-scrollbar space-y-6 pb-6 min-h-0">
              {!report && (
                <div className="bg-surface rounded-xl border border-border p-8 text-center text-sm text-gray-500">
                  Sube un documento para ver su estructura y el contenido ya parseado.
                </div>
              )}

              {report && (
                <>
                  {report.nombre_curso && report.nombre_curso !== "Nombre no encontrado" && (
                    <div className="flex items-center space-x-3">
                      <FileText className="w-6 h-6 text-primary" />
                      <h2 className="text-xl font-bold text-white">Curso: <span className="text-primary">{report.nombre_curso}</span></h2>
                    </div>
                  )}

                  <div className="bg-surface rounded-xl border border-border overflow-hidden shadow-md">
                    <div className="p-4 bg-background border-b border-border">
                      <h3 className="font-semibold text-white">Introducción General</h3>
                    </div>
                    <div className="p-1">
                      {renderItem(
                        'Presentación del espacio académico',
                        report.introduccion_general?.encontrado,
                        report.introduccion_general?.detalles,
                        report.introduccion_general?.encontrado
                          ? { target: fragmentTargetFor('introduccion', {}), title: 'Introducción General' }
                          : null
                      )}
                    </div>
                  </div>

                  <div className="bg-surface rounded-xl border border-border overflow-hidden shadow-md">
                    <div className="p-4 bg-background border-b border-border flex items-center">
                      <BookOpen className="w-4 h-4 text-primary mr-2" />
                      <h3 className="font-semibold text-white">Glosario</h3>
                    </div>
                    <div className="p-1">
                      <button
                        type="button"
                        onClick={() => setFragment({ target: fragmentTargetFor('glosario', {}), title: 'Glosario (XML de importación)' })}
                        className="w-full text-left hover:bg-primary/5 transition-colors"
                      >
                        <div className="flex items-start p-3 border-t border-border mt-3">
                          <div className="flex-1">
                            <div className="flex items-center justify-between">
                              <h4 className="text-sm font-semibold text-white">Entradas del glosario</h4>
                              <span className="flex items-center text-[10px] text-primary"><Eye className="w-3 h-3 mr-1" /> Ver XML</span>
                            </div>
                            <p className="text-xs text-gray-400 mt-1">Si el documento tiene un glosario, aquí se muestra el XML de importación real.</p>
                          </div>
                        </div>
                      </button>
                    </div>
                  </div>

                  {report.unidades && Object.keys(report.unidades).length > 0 ? (
                    Object.entries(report.unidades).map(([num, unit]) => {
                      const isComplete = unit.resumen?.encontrado &&
                        unit.preguntas_orientadoras?.encontrado &&
                        Object.keys(unit.actividades).length > 0 &&
                        unit.material_referencia?.encontrado;

                      return (
                        <div key={num} className="bg-surface rounded-xl border border-border overflow-hidden shadow-md">
                          <div className="p-4 bg-background border-b border-border flex items-center justify-between">
                            <h3 className="font-semibold text-white">Unidad Didáctica {num}</h3>
                            {isComplete ? (
                              <span className="flex items-center text-xs font-bold text-success bg-success/10 px-2 py-1 rounded border border-success/20">
                                <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Completo
                              </span>
                            ) : (
                              <span className="flex items-center text-xs font-bold text-error bg-error/10 px-2 py-1 rounded border border-error/20">
                                <XCircle className="w-3.5 h-3.5 mr-1" /> Incompleto
                              </span>
                            )}
                          </div>
                          <div className="p-1">
                            {renderItem('Resumen', unit.resumen?.encontrado, unit.resumen?.detalles)}
                            {renderItem('Preguntas Orientadoras', unit.preguntas_orientadoras?.encontrado,
                              unit.preguntas_orientadoras?.encontrado ? `Encontrado (${unit.preguntas_orientadoras.cantidad} preguntas)` : unit.preguntas_orientadoras?.detalles
                            )}

                            <div className="p-3 border-t border-border mt-3">
                              <div className="flex items-center justify-between mb-2">
                                <h4 className="text-sm font-semibold text-white">
                                  Actividades {Object.keys(unit.actividades).length > 0 ? `(${Object.keys(unit.actividades).length})` : ''}
                                </h4>
                                <span className="text-[10px] text-gray-500">Desmarca para excluir de la subida</span>
                              </div>
                              {Object.keys(unit.actividades).length > 0 ? (
                                <div className="flex flex-col gap-1.5">
                                  {Object.entries(unit.actividades).map(([id, act]) => {
                                    const isSkipped = skipped.has(id);
                                    const tipoLower = act.tipo?.toLowerCase();
                                    let colorClass = 'text-gray-300';
                                    if (tipoLower === 'no sabe' || tipoLower === 'desconocido') colorClass = 'text-error';
                                    else if (tipoLower === 'foro') colorClass = 'text-blue-400';
                                    else if (tipoLower === 'tarea') colorClass = 'text-purple-400';
                                    else if (tipoLower === 'cuestionario') colorClass = 'text-warning';

                                    return (
                                      <div
                                        key={id}
                                        className={`flex items-center justify-between rounded border px-2.5 py-1.5 transition-colors ${isSkipped ? 'border-border/50 bg-background/40 opacity-60' : 'border-border bg-background/80'}`}
                                      >
                                        <label className="flex items-center flex-1 cursor-pointer select-none min-w-0">
                                          <input
                                            type="checkbox"
                                            checked={!isSkipped}
                                            onChange={() => toggleSkip(id)}
                                            className="mr-2.5 shrink-0"
                                          />
                                          <span className={`text-[11px] font-medium truncate ${colorClass}`}>
                                            Actividad {id} - {act.tipo}
                                          </span>
                                          {isSkipped && <span className="ml-2 text-[10px] text-gray-500 shrink-0">(excluida)</span>}
                                        </label>
                                        <button
                                          type="button"
                                          onClick={() => setFragment({
                                            target: fragmentTargetFor('actividad', { num: id }),
                                            title: `Actividad ${id} — ${act.tipo} (Unidad ${num})`
                                          })}
                                          className="flex items-center text-[10px] text-primary hover:underline ml-2 shrink-0"
                                        >
                                          <Eye className="w-3 h-3 mr-1" /> Ver parseo
                                        </button>
                                      </div>
                                    );
                                  })}
                                </div>
                              ) : (
                                <p className="text-xs text-gray-500">Ninguna actividad encontrada.</p>
                              )}
                            </div>

                            {renderItem('Material de Referencia', unit.material_referencia?.encontrado, unit.material_referencia?.detalles,
                              unit.material_referencia?.encontrado
                                ? { target: fragmentTargetFor('material', { unit: num }), title: `Material de Referencia — Unidad ${num}` }
                                : null
                            )}
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div className="bg-surface rounded-xl border border-border overflow-hidden shadow-md">
                      <div className="p-4 bg-background border-b border-border">
                        <h3 className="font-semibold text-white">Unidades Didácticas</h3>
                      </div>
                      <div className="p-1">
                        {renderItem('Estructura de Unidades', false, 'No se encontró ninguna Unidad Didáctica en el documento.')}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          ) : (
            <div className="flex-1 flex flex-col min-h-0">
              <div className="flex bg-surface rounded-t-xl border border-border border-b-0 overflow-hidden shrink-0">
                {WORKFLOW_PHASES.map((phase, idx) => (
                  <button
                    key={phase.id}
                    className={`flex-1 py-2.5 px-1 text-[10px] sm:text-[11px] font-bold text-center uppercase tracking-tight transition-colors border-b-2 ${activeLogTab === idx ? 'bg-[#1e2638] text-primary border-primary' : 'bg-surface text-gray-500 border-transparent'}`}
                  >
                    <span className="truncate block w-full">{phase.shortTitle}</span>
                  </button>
                ))}
              </div>

              <div className="flex-1 bg-[#0f141f] rounded-b-xl border border-border flex flex-col relative shadow-inner min-h-0">
                <div className="flex items-center px-4 py-2 border-b border-white/5 bg-black/20 shrink-0">
                  <Terminal className="w-4 h-4 text-gray-400 mr-2" />
                  <h2 className="text-xs font-semibold text-gray-300 uppercase tracking-widest">Terminal de Moodle</h2>
                </div>

                <div className="flex-1 p-4 overflow-y-auto font-mono text-[13px] leading-relaxed space-y-2">
                  {logs.filter(l => l.phase === activeLogTab).length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-gray-600">
                      <Activity className="w-8 h-8 mb-3 opacity-20" />
                      <p>Esperando datos para esta fase...</p>
                    </div>
                  ) : (
                    logs.filter(l => l.phase === activeLogTab).map((logObj, i) => {
                      const log = logObj.text;
                      let color = 'text-gray-300';
                      let icon = <span className="text-gray-600 mr-2">·</span>;
                      const lower = log.toLowerCase();
                      if (lower.includes("error") || lower.includes("fail") || lower.includes("exception")) {
                        color = 'text-error'; icon = <span className="text-error mr-2">✖</span>;
                      } else if (lower.includes("warning") || lower.includes("skip")) {
                        color = 'text-warning'; icon = <span className="text-warning mr-2">⚠</span>;
                      } else if (lower.includes("success") || lower.includes("éxito") || lower.includes("ok") || lower.includes("completad")) {
                        color = 'text-success'; icon = <span className="text-success mr-2">✓</span>;
                      } else if (lower.includes("sistema") || lower.includes("iniciando")) {
                        color = 'text-primary'; icon = <span className="text-primary mr-2">➜</span>;
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
            </div>
          )}
        </div>
      </main>

      {fragment && (
        <FragmentViewer
          target={fragment.target}
          title={fragment.title}
          courseId={courseId}
          onClose={() => setFragment(null)}
        />
      )}
    </div>
  );
}
