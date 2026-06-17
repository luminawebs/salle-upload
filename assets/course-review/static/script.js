document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadContent = document.querySelector('.upload-content');
    const loadingState = document.getElementById('loading-state');
    const resultsContainer = document.getElementById('results-container');

    // Drag & Drop Events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('dragover');
        }, false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length) handleFiles(files);
    }, false);

    // Click to upload
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', function() {
        if (this.files.length) handleFiles(this.files);
    });

    function handleFiles(files) {
        const file = files[0];
        
        if (!file.name.endsWith('.docx')) {
            alert('Por favor sube un archivo .docx válido');
            return;
        }

        uploadFile(file);
    }

    async function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        // Show loading state
        uploadContent.classList.add('hidden');
        loadingState.classList.remove('hidden');
        resultsContainer.innerHTML = '';
        resultsContainer.classList.add('hidden');

        try {
            const response = await fetch('/api/review', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Error procesando el documento');
            }

            renderResults(data);
        } catch (error) {
            alert(error.message);
        } finally {
            // Restore upload zone
            loadingState.classList.add('hidden');
            uploadContent.classList.remove('hidden');
        }
    }

    function renderResults(data) {
        resultsContainer.innerHTML = '';
        
        // Render Course Name Title
        if (data.nombre_curso && data.nombre_curso !== "Nombre no encontrado") {
            const courseTitle = document.createElement('h2');
            courseTitle.className = 'course-title';
            courseTitle.textContent = `Curso: ${data.nombre_curso}`;
            resultsContainer.appendChild(courseTitle);
        }
        
        // Render Intro Card
        const intro = data.introduccion_general;
        const introCard = createCard(
            'Introducción General',
            intro.encontrado,
            [{
                title: 'Presentación del espacio académico',
                desc: intro.detalles,
                success: intro.encontrado
            }]
        );
        resultsContainer.appendChild(introCard);

        let hasNoSabe = false;

        // Render Units
        if (data.unidades && Object.keys(data.unidades).length > 0) {
            Object.entries(data.unidades).forEach(([num, unit]) => {
                const isComplete = unit.resumen.encontrado && 
                                   unit.preguntas_orientadoras.encontrado && 
                                   Object.keys(unit.actividades).length > 0 && 
                                   unit.material_referencia.encontrado;

                Object.values(unit.actividades).forEach(act => {
                    if (act.tipo === 'No sabe') hasNoSabe = true;
                });

                const items = [
                    { title: 'Resumen', desc: unit.resumen.detalles, success: unit.resumen.encontrado },
                    { title: 'Preguntas Orientadoras', desc: unit.preguntas_orientadoras.encontrado ? `Encontrado (${unit.preguntas_orientadoras.cantidad} preguntas)` : unit.preguntas_orientadoras.detalles, success: unit.preguntas_orientadoras.encontrado },
                    { 
                        title: 'Actividades', 
                        desc: Object.keys(unit.actividades).length > 0 ? `${Object.keys(unit.actividades).length} encontradas` : 'Ninguna actividad encontrada', 
                        success: Object.keys(unit.actividades).length > 0,
                        tags: Object.entries(unit.actividades).map(([id, act]) => ({ 
                            id, 
                            tipo: act.tipo, 
                            cantidad_preguntas: act.cantidad_preguntas 
                        }))
                    },
                    { title: 'Material de Referencia', desc: unit.material_referencia.detalles, success: unit.material_referencia.encontrado }
                ];

                const unitCard = createCard(`Unidad Didáctica ${num}`, isComplete, items);
                resultsContainer.appendChild(unitCard);
            });
        } else {
            const errorCard = createCard('Unidades Didácticas', false, [{
                title: 'Estructura de Unidades',
                desc: 'No se encontró ninguna Unidad Didáctica en el documento.',
                success: false
            }]);
            resultsContainer.appendChild(errorCard);
        }

        if (hasNoSabe) {
            const alertDiv = document.createElement('div');
            alertDiv.className = 'alert alert-warning';
            alertDiv.innerHTML = '<strong>¡Atención!</strong> Se encontró al menos una actividad marcada como "No sabe" en la herramienta virtual.';
            resultsContainer.insertBefore(alertDiv, resultsContainer.firstChild); // Place at the very top
        }

        resultsContainer.classList.remove('hidden');
    }

    function createCard(title, isSuccess, items) {
        const card = document.createElement('div');
        card.className = 'card';

        const statusClass = isSuccess ? 'status-success' : 'status-error';
        const statusIcon = isSuccess ? '✓' : 'X';
        const statusText = isSuccess ? 'Completo' : 'Incompleto';

        let itemsHtml = items.map(item => `
            <div class="item">
                <div class="item-icon ${item.success ? 'icon-success' : 'icon-error'}">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                        ${item.success ? '<polyline points="20 6 9 17 4 12"></polyline>' : '<line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>'}
                    </svg>
                </div>
                <div class="item-content">
                    <div class="item-title">${item.title}</div>
                    <div class="item-desc">${item.desc}</div>
                    ${item.tags && item.tags.length > 0 ? `
                        <div class="activities-tags">
                            ${item.tags.map(t => {
                                let tagClass = 'tag';
                                if (t.tipo === 'No sabe') {
                                    tagClass += ' tag-alert';
                                } else if (t.tipo === 'Foro') {
                                    tagClass += ' tag-foro';
                                } else if (t.tipo === 'Tarea') {
                                    tagClass += ' tag-tarea';
                                } else if (t.tipo === 'Cuestionario') {
                                    tagClass += ' tag-cuestionario';
                                }
                                
                                let tagText = `Actividad ${t.id} - ${t.tipo}`;
                                if (t.cantidad_preguntas > 0) {
                                    tagText += ` Preguntas: ${t.cantidad_preguntas}`;
                                }
                                return `<span class="${tagClass}">${tagText}</span>`;
                            }).join('')}
                        </div>
                    ` : ''}
                </div>
            </div>
        `).join('');

        card.innerHTML = `
            <div class="card-header">
                <div class="card-title">${title}</div>
                <div class="status-badge ${statusClass}">
                    <span>${statusIcon}</span> ${statusText}
                </div>
            </div>
            <div class="item-list">
                ${itemsHtml}
            </div>
        `;

        return card;
    }
});
