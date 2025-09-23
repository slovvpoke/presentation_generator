// Link counter functionality
function updateLinkCounter() {
    const textarea = document.getElementById('app_links');
    const counter = document.getElementById('link-counter');
    
    if (textarea && counter) {
        const links = textarea.value.trim().split('\n').filter(link => link.trim());
        const count = links.length;
        
        if (count === 0) {
            counter.textContent = '';
        } else {
            counter.textContent = `(${count} links)`;
            counter.className = 'text-success';
        }
    }
}

// Initialize link counter when page loads
document.addEventListener('DOMContentLoaded', function() {
    const textarea = document.getElementById('app_links');
    if (textarea) {
        textarea.addEventListener('input', updateLinkCounter);
        textarea.addEventListener('paste', function() {
            // Update counter after paste event is processed
            setTimeout(updateLinkCounter, 100);
        });
        updateLinkCounter(); // Initial count
    }
});

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
    const textarea = document.getElementById('app_links');
    
    // Validate textarea manually
    if (!textarea.value.trim()) {
        alert('Please enter at least one AppExchange link');
        textarea.focus();
        return;
    }
    
    const links = textarea.value.trim().split('\n').filter(link => link.trim());
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
    
    const textarea = document.getElementById('app_links');
    const links = textarea.value.trim().split('\n').filter(link => link.trim());
    
    // If form is valid, show preview automatically
    previewPresentation();
});

// Real-time validation
document.getElementById('industry').addEventListener('input', function() {
    this.value = this.value.replace(/[^a-zA-Zа-яёА-ЯЁ\s]/g, '');
});