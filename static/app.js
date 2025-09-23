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
                    <i class="fas fa-edit"></i> Override
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
                           name="app_names[]" placeholder="Application Name">
                </div>
                <div class="col-md-4">
                    <input type="text" class="form-control form-control-sm" 
                           name="app_developers[]" placeholder="Developer">
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
    
    // Limit on maximum number of links
    if (container.children.length >= 20) {
        document.querySelector('button[onclick="addLink()"]').disabled = true;
    }
}

function removeLink(index) {
    const linkItem = document.querySelector(`[data-index="${index}"]`);
    if (linkItem) {
        linkItem.remove();
        
        // Enable add button if number of links becomes less than 20
        const container = document.getElementById('linksContainer');
        if (container.children.length < 20) {
            document.querySelector('button[onclick="addLink()"]').disabled = false;
        }
        
        // Check minimum number of links
        if (container.children.length < 1) {
            alert('Enter at least one link to create a presentation');
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
            alert('Error creating preview: ' + data.error);
        }
    })
    .catch(error => {
        hideLoading();
        alert('Error: ' + error.message);
    });
}

function showPreview(previewData) {
    const previewContent = document.getElementById('previewContent');
    let html = '';
    
    let hasWarnings = false;
    
    previewData.slides.forEach((slide, index) => {
        const isWarning = slide.content && slide.content.includes('⚠️ Manual input required');
        if (isWarning) hasWarnings = true;
        
        html += `
            <div class="slide-preview ${isWarning ? 'border-warning' : ''}">
                <h5><i class="fas fa-file-powerpoint"></i> Slide ${index + 1}: ${slide.title}</h5>
                ${isWarning ? '<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> This slide requires manual data input</div>' : ''}
                <div class="row">
                    ${slide.content ? `<div class="col-md-8">${slide.content}</div>` : ''}
                    ${slide.image ? `<div class="col-md-4"><img src="${slide.image}" class="img-fluid rounded" alt="Logo"></div>` : ''}
                </div>
            </div>
        `;
    });
    
    if (hasWarnings) {
        html = `
            <div class="alert alert-info">
                <h6><i class="fas fa-info-circle"></i> Attention!</h6>
                <p>For some applications, data could not be automatically extracted. 
                Use the "Override" button next to corresponding links for manual input:</p>
                <ul class="mb-0">
                    <li>Application name</li>
                    <li>Developer</li>
                    <li>Logo (image file)</li>
                </ul>
            </div>
        ` + html;
    }
    
    previewContent.innerHTML = html;
    document.getElementById('previewSection').style.display = 'block';
    
    // Scroll to preview
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
            throw new Error('Error generating file');
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
        alert('Download error: ' + error.message);
    });
}

// Form submission handler
document.getElementById('presentationForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const container = document.getElementById('linksContainer');
    if (container.children.length < 1) {
        alert('At least 1 link is required to create a presentation');
        return;
    }
    
    // If form is valid, show preview automatically
    previewPresentation();
});

// Real-time validation
document.getElementById('industry').addEventListener('input', function() {
    this.value = this.value.replace(/[^a-zA-Zа-яёА-ЯЁ\s]/g, '');
});

// Automatic link addition on startup
document.addEventListener('DOMContentLoaded', function() {
    // Add 4 more link fields by default (total will be 5)
    for (let i = 0; i < 4; i++) {
        addLink();
    }
});