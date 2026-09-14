import React, { useContext, useState } from 'react';
import {
  Upload, CheckCircle2, FileText, AlertTriangle, RefreshCw, XCircle,
  Code2, Eye, X, BookOpen
} from 'lucide-react';
import NavigationTabs from './NavigationTabs';
import AutomationControls from './AutomationControls';
import { AutomationContext } from '../context/AutomationContext';

const API_BASE = import.meta.env.VITE_API_BASE || "";

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

  React.useEffect(() => {
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

export default function UnifiedAnalyzerView({ setActiveTab }) {
  const {
    settings, handleSetSetting, handleSaveSettings,
    status: runStatus, uploadedCourseId, setUploadedCourseId
  } = useContext(AutomationContext);

  const [uploadStatus, setUploadStatus] = useState('idle'); // idle, loading, done, error
  const [errorMsg, setErrorMsg] = useState('');
  const [report, setReport] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [fragment, setFragment] = useState(null); // { target, title }

  const courseId = (settings.COURSES_TO_PROCESS || '').trim();

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

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("course_id", courseId);

    try {
      const response = await fetch(`${API_BASE}/api/upload`, { method: 'POST', body: formData });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Error procesando el documento');

      setReport(data.report || null);
      setUploadedCourseId(courseId);
      setUploadStatus('done');
    } catch (err) {
      console.error(err);
      setErrorMsg(err.message);
      setUploadStatus('error');
    }
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

  // Clickable chip: fetches and shows the real parsed fragment for this item.
  const Clickable = ({ kind, params, title, children }) => {
    const target = fragmentTargetFor(kind, params);
    if (!target) return children;
    return (
      <button
        type="button"
        onClick={() => setFragment({ target, title })}
        className="text-left w-full hover:bg-primary/5 rounded-lg transition-colors"
        title="Ver cómo se parseó este elemento"
      >
        {children}
      </button>
    );
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
    <div className="min-h-screen bg-background text-gray-200 font-sans flex flex-col">
      <header className="h-16 bg-surface border-b border-border flex items-center justify-between px-6 sticky top-0 z-10">
        <div className="flex items-center space-x-6">
          <img src="/logo.png" alt="La Salle" className="h-8 object-contain" />
          <div className="h-6 w-px bg-border"></div>
          <h1 className="text-lg font-bold tracking-tight text-white">Moodle Automation Engine</h1>
          <div className="h-6 w-px bg-border ml-4 mr-2"></div>
          <NavigationTabs activeTab="unified" setActiveTab={setActiveTab} />
        </div>
      </header>

      <main className="flex-1 p-6 max-w-6xl mx-auto w-full grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left: upload + report (Revisor idea) */}
        <div className="lg:col-span-2 flex flex-col space-y-6">
          <div className="bg-surface rounded-xl border border-border p-6 shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold text-white">Analizar documento</h2>
                <p className="text-sm text-gray-400">Sube el .docx del curso para ver su estructura y el contenido ya parseado.</p>
              </div>
            </div>

            <div className="flex flex-col space-y-1 mb-4">
              <label className="text-xs font-semibold text-gray-300 uppercase tracking-wide">ID de Curso</label>
              <input
                type="text"
                value={settings.COURSES_TO_PROCESS}
                onChange={(e) => handleSetSetting('COURSES_TO_PROCESS', e.target.value)}
                disabled={runStatus === 'Running'}
                className="w-full bg-surface/50 border border-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-primary transition-colors disabled:opacity-50"
                placeholder="Ej: 70801"
              />
            </div>

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

            {uploadStatus === 'error' && (
              <div className="mt-4 p-3 rounded-lg bg-error/10 border border-error/30 flex items-start text-error text-sm">
                <AlertTriangle className="w-5 h-5 mr-2 flex-shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}
            {uploadStatus === 'done' && (
              <p className="mt-3 text-xs text-gray-500">
                Haz clic en cualquier elemento marcado con <Eye className="w-3 h-3 inline mx-0.5 text-primary" /> "Ver parseo" para ver el HTML/XML real que se extrajo.
              </p>
            )}
          </div>

          {report && (
            <div className="space-y-6 pb-6">
              {report.nombre_curso && report.nombre_curso !== "Nombre no encontrado" && (
                <div className="flex items-center space-x-3">
                  <FileText className="w-6 h-6 text-primary" />
                  <h2 className="text-xl font-bold text-white">Curso: <span className="text-primary">{report.nombre_curso}</span></h2>
                </div>
              )}

              {/* Introducción General */}
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

              {/* Glosario, if the parser found one for this course */}
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

              {/* Unidades */}
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

                        {/* Actividades: each one opens its real parsed HTML */}
                        <div className="p-3 border-t border-border mt-3">
                          <h4 className="text-sm font-semibold text-white mb-2">
                            Actividades {Object.keys(unit.actividades).length > 0 ? `(${Object.keys(unit.actividades).length})` : ''}
                          </h4>
                          {Object.keys(unit.actividades).length > 0 ? (
                            <div className="flex flex-wrap gap-2">
                              {Object.entries(unit.actividades).map(([id, act]) => {
                                const tipoLower = act.tipo?.toLowerCase();
                                let colorClass = 'bg-surface border-border text-gray-300';
                                if (tipoLower === 'no sabe' || tipoLower === 'desconocido') colorClass = 'bg-error/20 border-error/50 text-error';
                                else if (tipoLower === 'foro') colorClass = 'bg-blue-500/20 border-blue-500/50 text-blue-400';
                                else if (tipoLower === 'tarea') colorClass = 'bg-purple-500/20 border-purple-500/50 text-purple-400';
                                else if (tipoLower === 'cuestionario') colorClass = 'bg-warning/20 border-warning/50 text-warning';

                                return (
                                  <button
                                    key={id}
                                    type="button"
                                    onClick={() => setFragment({
                                      target: fragmentTargetFor('actividad', { num: id }),
                                      title: `Actividad ${id} — ${act.tipo} (Unidad ${num})`
                                    })}
                                    className={`flex items-center text-[11px] px-2.5 py-1 rounded border font-medium hover:brightness-125 transition-all ${colorClass}`}
                                  >
                                    <Eye className="w-3 h-3 mr-1.5" />
                                    Actividad {id} - {act.tipo}
                                  </button>
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
            </div>
          )}
        </div>

        {/* Right: run controls (Tracker idea) */}
        <div className="flex flex-col gap-6">
          <AutomationControls />
          <div className="bg-surface rounded-xl border border-border p-4 shadow-sm text-xs text-gray-400 leading-relaxed">
            Esta pestaña es una prueba que unifica el Revisor de Documentos y el Tracker:
            analiza el documento, muestra el contenido realmente parseado por cada
            elemento, y desde el mismo lugar puedes lanzar la automatización una vez
            verificado.
          </div>
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
