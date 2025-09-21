let linkCounter = 1;

function addLink() {
    const container = document.getElementById('linksContainer');
    const linkDiv = document.createElement('div');
    linkDiv.className = 'link-item';
    linkDiv.setAttribute('data-index', linkCounter);
    
    linkDiv.innerHTML = `
        <div class="row">
            <div class="col-md-8">
                <input type="url" class="form-control" name="app_links[]" 
                       placeholder="https://appexchange.salesforce.com/..." required>
            </div>
            <div class="col-md-4 text-end">
                <button type="button" class="btn btn-sm btn-outline-secondary" onclick="toggleOverride(${linkCounter})">
                    <i class="fas fa-edit"></i> Переопределить
                </button>
                <button type="button" class="btn btn-sm btn-danger" onclick="removeLink(${linkCounter})">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
        <div class="app-override" id="override-${linkCounter}" style="display: none;">
            <div class="row">
                <div class="col-md-4">
                    <input type="text" class="form-control form-control-sm" 
                           name="app_names[]" placeholder="Название приложения">
                </div>
                <div class="col-md-4">
                    <input type="text" class="form-control form-control-sm" 
                           name="app_developers[]" placeholder="Разработчик">
                </div>
                <div class="col-md-4">
                    <input type="file" class="form-control form-control-sm" 
                           name="app_logos[]" accept="image/*">
                </div>
            </div>
        </div>
    `;
    
    container.appendChild(linkDiv);
    linkCounter++;
    
    // Ограничение на максимальное количество ссылок
    if (container.children.length >= 20) {
        document.querySelector('button[onclick="addLink()"]').disabled = true;
    }
}

function removeLink(index) {
    const linkItem = document.querySelector(`[data-index="${index}"]`);
    if (linkItem) {
        linkItem.remove();
        
        // Включить кнопку добавления, если количество ссылок стало меньше 20
        const container = document.getElementById('linksContainer');
        if (container.children.length < 20) {
            document.querySelector('button[onclick="addLink()"]').disabled = false;
        }
        
        // Проверить минимальное количество ссылок
        if (container.children.length < 5) {
            alert('Необходимо минимум 5 ссылок для создания презентации');
        }
    }
}

function toggleOverride(index) {
    const overrideDiv = document.getElementById(`override-${index}`);
    if (overrideDiv.style.display === 'none' || overrideDiv.style.display === '') {
        overrideDiv.style.display = 'block';
    } else {
        overrideDiv.style.display = 'none';
    }
}

function showLoading() {
    document.getElementById('loadingIndicator').style.display = 'block';
    document.getElementById('presentationForm').style.display = 'none';
}

function hideLoading() {
    document.getElementById('loadingIndicator').style.display = 'none';
    document.getElementById('presentationForm').style.display = 'block';
}

function previewPresentation() {
    const form = document.getElementById('presentationForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }
    
    showLoading();
    
    const formData = new FormData(form);
    formData.append('preview', 'true');
    
    fetch('/generate', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        if (data.success) {
            showPreview(data.preview);
        } else {
            alert('Ошибка при создании превью: ' + data.error);
        }
    })
    .catch(error => {
        hideLoading();
        alert('Ошибка: ' + error.message);
    });
}

function showPreview(previewData) {
    const previewContent = document.getElementById('previewContent');
    let html = '';
    
    let hasWarnings = false;
    
    previewData.slides.forEach((slide, index) => {
        const isWarning = slide.content && slide.content.includes('⚠️ Требуется ручной ввод');
        if (isWarning) hasWarnings = true;
        
        html += `
            <div class="slide-preview ${isWarning ? 'border-warning' : ''}">
                <h5><i class="fas fa-file-powerpoint"></i> Слайд ${index + 1}: ${slide.title}</h5>
                ${isWarning ? '<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> Для этого слайда требуется ручной ввод данных</div>' : ''}
                <div class="row">
                    ${slide.content ? `<div class="col-md-8">${slide.content}</div>` : ''}
                    ${slide.image ? `<div class="col-md-4"><img src="${slide.image}" class="img-fluid rounded" alt="Логотип"></div>` : ''}
                </div>
            </div>
        `;
    });
    
    if (hasWarnings) {
        html = `
            <div class="alert alert-info">
                <h6><i class="fas fa-info-circle"></i> Внимание!</h6>
                <p>Для некоторых приложений не удалось автоматически извлечь данные. 
                Используйте кнопку "Переопределить" рядом с соответствующими ссылками для ручного ввода:</p>
                <ul class="mb-0">
                    <li>Название приложения</li>
                    <li>Разработчик</li>
                    <li>Логотип (файл изображения)</li>
                </ul>
            </div>
        ` + html;
    }
    
    previewContent.innerHTML = html;
    document.getElementById('previewSection').style.display = 'block';
    
    // Прокрутить к превью
    document.getElementById('previewSection').scrollIntoView({ behavior: 'smooth' });
}

function downloadPPTX() {
    const form = document.getElementById('presentationForm');
    const formData = new FormData(form);
    formData.append('format', 'pptx');
    
    downloadFile(formData, 'pptx');
}

function downloadPDF() {
    const form = document.getElementById('presentationForm');
    const formData = new FormData(form);
    formData.append('format', 'pdf');
    
    downloadFile(formData, 'pdf');
}

function downloadFile(formData, format) {
    showLoading();
    
    fetch('/generate', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (response.ok) {
            return response.blob();
        } else {
            throw new Error('Ошибка при генерации файла');
        }
    })
    .then(blob => {
        hideLoading();
        
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        
        const industry = document.getElementById('industry').value;
        const filename = `Best_Apps_for_${industry}.${format}`;
        a.download = filename;
        
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    })
    .catch(error => {
        hideLoading();
        alert('Ошибка при скачивании: ' + error.message);
    });
}

// Обработчик отправки формы
document.getElementById('presentationForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const container = document.getElementById('linksContainer');
    if (container.children.length < 1) {
        alert('Необходимо минимум 1 ссылку для создания презентации');
        return;
    }
    
    // Если форма валидна, показать превью автоматически
    previewPresentation();
});

// Валидация в реальном времени
document.getElementById('industry').addEventListener('input', function() {
    this.value = this.value.replace(/[^a-zA-Zа-яёА-ЯЁ\s]/g, '');
});

// Автоматическое добавление ссылок при запуске
document.addEventListener('DOMContentLoaded', function() {
    // Добавить еще 4 поля ссылок по умолчанию (всего будет 5)
    for (let i = 0; i < 4; i++) {
        addLink();
    }
});