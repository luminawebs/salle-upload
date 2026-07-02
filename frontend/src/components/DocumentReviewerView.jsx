import React, { useState } from 'react';
import { Upload, CheckCircle2, FileText, AlertTriangle, RefreshCw, XCircle, Check } from 'lucide-react';
import NavigationTabs from './NavigationTabs';

// const API_BASE = "http://127.0.0.1:8000";
// const API_BASE = "http://157.230.50.37:8000";
// const API_BASE = window.location.origin;
const API_BASE = import.meta.env.VITE_API_BASE || "";

export default function DocumentReviewerView({ setActiveTab }) {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState('idle'); // idle, loading, done, error
  const [errorMsg, setErrorMsg] = useState('');
  const [report, setReport] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

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

  const handleUpload = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      processFile(e.target.files[0]);
    }
    e.target.value = null;
  };

  const processFile = async (selectedFile) => {
    if (!selectedFile.name.endsWith('.docx')) {
      setErrorMsg('Por favor sube un archivo .docx válido.');
      setStatus('error');
      return;
    }

    setFile(selectedFile);
    setStatus('loading');
    setErrorMsg('');
    setReport(null);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await fetch(`${API_BASE}/api/review`, {
        method: 'POST',
        body: formData
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Error procesando el documento');
      }

      setReport(data);
      setStatus('done');
    } catch (err) {
      console.error(err);
      setErrorMsg(err.message);
      setStatus('error');
    }
  };

  // Helper to render items
  const renderItem = (title, success, desc, tags = []) => (
    <div className="flex items-start p-3 border-t border-border mt-3">
      <div className={`mt-0.5 mr-3 flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center ${success ? 'bg-success/20 text-success' : 'bg-error/20 text-error'}`}>
        {success ? <Check className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
      </div>
      <div className="flex-1">
        <h4 className="text-sm font-semibold text-white">{title}</h4>
        <p className="text-xs text-gray-400 mt-1">{desc}</p>
        {tags.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {tags.map((t, idx) => {
              let colorClass = 'bg-surface border-border text-gray-300';
              if (t.tipo === 'No sabe') colorClass = 'bg-error/20 border-error/50 text-error';
              else if (t.tipo === 'Foro') colorClass = 'bg-blue-500/20 border-blue-500/50 text-blue-400';
              else if (t.tipo === 'Tarea') colorClass = 'bg-purple-500/20 border-purple-500/50 text-purple-400';
              else if (t.tipo === 'Cuestionario') colorClass = 'bg-warning/20 border-warning/50 text-warning';

              return (
                <span key={idx} className={`text-[10px] px-2 py-0.5 rounded border font-medium ${colorClass}`}>
                  Actividad {t.id} - {t.tipo} {t.cantidad_preguntas > 0 ? `(${t.cantidad_preguntas} preg)` : ''}
                </span>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );

  let hasNoSabe = false;
  if (report && report.unidades) {
    Object.values(report.unidades).forEach(unit => {
      Object.values(unit.actividades).forEach(act => {
        if (act.tipo === 'No sabe') hasNoSabe = true;
      });
    });
  }

  return (
    <div className="min-h-screen bg-background text-gray-200 font-sans flex flex-col">
      {/* Header */}
      <header className="h-16 bg-surface border-b border-border flex items-center justify-between px-6 sticky top-0 z-10">
        <div className="flex items-center space-x-6">
          <img src="/logo.png" alt="La Salle" className="h-8 object-contain" />
          <div className="h-6 w-px bg-border"></div>
          <h1 className="text-lg font-bold tracking-tight text-white flex items-center">
            Revisor de Documentos
            <span className="ml-3 px-2 py-0.5 rounded text-xs font-semibold bg-blue-500/20 text-blue-400 border border-blue-500/30">Validador</span>
          </h1>
          <div className="h-6 w-px bg-border ml-4 mr-2"></div>
          <NavigationTabs activeTab="reviewer" setActiveTab={setActiveTab} />
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 p-6 max-w-5xl mx-auto w-full flex flex-col space-y-6">

        {/* Upload Zone */}
        <div className="bg-surface rounded-xl border border-border p-6 shadow-lg">
          <div className="mb-4">
            <h2 className="text-base font-semibold text-white">Sube tu archivo .docx</h2>
            <p className="text-sm text-gray-400">Verifica la estructura y elementos requeridos del documento de diseño de curso.</p>
          </div>

          <label
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`flex flex-col items-center justify-center w-full h-48 border-2 border-dashed rounded-xl cursor-pointer transition-all ${isDragging ? 'border-primary bg-primary/10' : status === 'loading' ? 'border-primary/50 bg-primary/5' : 'border-border hover:border-gray-500 hover:bg-surface/80'}`}
          >
            {status === 'loading' ? (
              <div className="flex flex-col items-center">
                <RefreshCw className="w-10 h-10 text-primary animate-spin mb-3" />
                <p className="text-sm font-medium text-white">Analizando documento...</p>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center text-center px-4">
                <Upload className="w-10 h-10 mb-3 text-gray-400 group-hover:text-primary transition-colors" />
                <p className="mb-2 text-sm text-gray-200"><span className="font-semibold text-primary">Arrastra tu archivo</span> o haz clic</p>
                <p className="text-xs text-gray-500">Solo documentos .docx</p>
              </div>
            )}
            <input type="file" accept=".docx" className="hidden" onChange={handleUpload} disabled={status === 'loading'} />
          </label>

          {status === 'error' && (
            <div className="mt-4 p-3 rounded-lg bg-error/10 border border-error/30 flex items-start text-error text-sm">
              <AlertTriangle className="w-5 h-5 mr-2 flex-shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}
        </div>

        {/* Results */}
        {report && (
          <div className="space-y-6 pb-12 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {hasNoSabe && (
              <div className="p-4 rounded-lg bg-warning/10 border border-warning/30 flex items-start text-warning">
                <AlertTriangle className="w-6 h-6 mr-3 flex-shrink-0" />
                <div>
                  <h3 className="font-bold text-sm">¡Atención!</h3>
                  <p className="text-xs mt-1">Se encontró al menos una actividad marcada como "No sabe" en la herramienta virtual. Por favor, revisa el documento.</p>
                </div>
              </div>
            )}

            {report.nombre_curso && report.nombre_curso !== "Nombre no encontrado" && (
              <div className="flex items-center space-x-3">
                <FileText className="w-6 h-6 text-primary" />
                <h2 className="text-xl font-bold text-white">Curso: <span className="text-primary">{report.nombre_curso}</span></h2>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

              {/* Introducción General */}
              <div className="bg-surface rounded-xl border border-border overflow-hidden shadow-md">
                <div className="p-4 bg-background border-b border-border flex items-center justify-between">
                  <h3 className="font-semibold text-white">Introducción General</h3>
                  {report.introduccion_general?.encontrado ? (
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
                  {renderItem(
                    'Presentación del espacio académico',
                    report.introduccion_general?.encontrado,
                    report.introduccion_general?.detalles
                  )}
                </div>
              </div>

              {/* Unidades */}
              {report.unidades && Object.keys(report.unidades).length > 0 ? (
                Object.entries(report.unidades).map(([num, unit]) => {
                  const isComplete = unit.resumen?.encontrado &&
                    unit.preguntas_orientadoras?.encontrado &&
                    Object.keys(unit.actividades).length > 0 &&
                    unit.material_referencia?.encontrado;

                  const activitiesTags = Object.entries(unit.actividades).map(([id, act]) => ({
                    id, tipo: act.tipo, cantidad_preguntas: act.cantidad_preguntas
                  }));

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
                        {renderItem('Actividades', Object.keys(unit.actividades).length > 0,
                          Object.keys(unit.actividades).length > 0 ? `${Object.keys(unit.actividades).length} encontradas` : 'Ninguna actividad encontrada',
                          activitiesTags
                        )}
                        {renderItem('Material de Referencia', unit.material_referencia?.encontrado, unit.material_referencia?.detalles)}
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
          </div>
        )}
      </main>
    </div>
  );
}
