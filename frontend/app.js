/**
 * URS Generator - Frontend Application
 * 
 * Handles:
 * - Navigation between views
 * - Form submission and file uploads
 * - API communication with backend
 * - Dynamic UI updates
 */

// ============================================================================
// Configuration
// ============================================================================

const API_BASE = window.APP_CONFIG?.API_BASE_URL || 'http://localhost:8000/api';

// ============================================================================
// State Management
// ============================================================================

const state = {
    currentView: 'intake',
    sessionId: null,
    ursId: null,
    questions: [],
    answers: {},
    urs: null,
    qaReport: null,
    files: []
};

// ============================================================================
// DOM Elements
// ============================================================================

const elements = {
    navButtons: document.querySelectorAll('.nav-btn'),
    views: document.querySelectorAll('.view'),
    sessionStatus: document.getElementById('session-status'),
    intakeForm: document.getElementById('intake-form'),
    fileInput: document.getElementById('file-input'),
    fileList: document.getElementById('file-list'),
    fileUploadZone: document.getElementById('file-upload-zone'),
    ursContent: document.getElementById('urs-content'),
    toastContainer: document.getElementById('toast-container'),
    // Collapsible sections
    toggleAdditional: document.getElementById('toggle-additional'),
    additionalContext: document.getElementById('additional-context')
};

// ============================================================================
// Navigation
// ============================================================================

function switchView(viewName) {
    state.currentView = viewName;
    
    // Update nav buttons
    elements.navButtons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === viewName);
    });
    
    // Update views
    elements.views.forEach(view => {
        view.classList.toggle('active', view.id === `view-${viewName}`);
    });
}

elements.navButtons.forEach(btn => {
    btn.addEventListener('click', () => switchView(btn.dataset.view));
});

// ============================================================================
// Tab Switching
// ============================================================================

const tabButtons = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');

tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        const tabId = btn.dataset.tab;
        
        // Update buttons
        tabButtons.forEach(b => b.classList.toggle('active', b === btn));
        
        // Update content
        tabContents.forEach(content => {
            content.classList.toggle('active', content.id === `tab-${tabId}`);
        });
    });
});

// ============================================================================
// Collapsible Sections
// ============================================================================

function setupCollapsibleSections() {
    // Additional Context toggle
    if (elements.toggleAdditional) {
        elements.toggleAdditional.addEventListener('click', () => {
            const section = elements.toggleAdditional.closest('.form-section');
            section.classList.toggle('open');
        });
    }
}

setupCollapsibleSections();

// ============================================================================
// File Upload
// ============================================================================

elements.fileUploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    elements.fileUploadZone.classList.add('dragover');
});

elements.fileUploadZone.addEventListener('dragleave', () => {
    elements.fileUploadZone.classList.remove('dragover');
});

elements.fileUploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    elements.fileUploadZone.classList.remove('dragover');
    handleFiles(e.dataTransfer.files);
});

elements.fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
});

// Click handler for browse button
const browseBtn = document.getElementById('browse-btn');
if (browseBtn) {
    console.log('Browse button found, attaching click handler');
    browseBtn.onclick = function(e) {
        console.log('Browse button clicked!');
        const input = document.getElementById('file-input');
        console.log('File input:', input);
        if (input) {
            input.click();
            console.log('Called input.click()');
        }
        return false; // Prevent any default behavior
    };
} else {
    console.log('Browse button NOT found');
}

// Click handler for entire upload zone
if (elements.fileUploadZone) {
    console.log('Upload zone found, attaching click handler');
    elements.fileUploadZone.addEventListener('click', function(e) {
        console.log('Upload zone clicked!', e.target);
        // Don't trigger if clicking on the file list or on the browse button
        if (!e.target.closest('.file-list') && e.target.id !== 'browse-btn') {
            const input = document.getElementById('file-input');
            if (input) {
                input.click();
                console.log('Called input.click() from zone');
            }
        }
    });
} else {
    console.log('Upload zone NOT found');
}

function handleFiles(files) {
    Array.from(files).forEach(file => {
        if (!state.files.find(f => f.name === file.name)) {
            state.files.push(file);
        }
    });
    renderFileList();
}

function renderFileList() {
    elements.fileList.innerHTML = state.files.map((file, index) => `
        <li>
            <span>${file.name} (${formatFileSize(file.size)})</span>
            <button class="file-remove" onclick="removeFile(${index})">×</button>
        </li>
    `).join('');
}

function removeFile(index) {
    state.files.splice(index, 1);
    renderFileList();
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ============================================================================
// Form Submission
// ============================================================================

elements.intakeForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const submitBtn = e.target.querySelector('button[type="submit"]');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnLoading = submitBtn.querySelector('.btn-loading');
    
    // Show loading state
    btnText.hidden = true;
    btnLoading.hidden = false;
    submitBtn.disabled = true;
    
    try {
        // Build form data
        const formData = new FormData(e.target);
        
        // Add files
        state.files.forEach(file => {
            formData.append('files', file);
        });
        
        // Submit to API for ingest
        const response = await fetch(`${API_BASE}/ingest`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(await response.text());
        }
        
        const result = await response.json();
        
        // Update state
        state.sessionId = result.session_id;
        state.ursId = result.urs_id;
        
        // Update UI
        updateSessionStatus(true);
        showToast('Analyzing requirements...', 'info');
        
        // Generate URS directly (skip clarifying questions)
        await generateURS(true);
        
    } catch (error) {
        console.error('Submission error:', error);
        showToast('Failed to submit request. Please try again.', 'error');
    } finally {
        btnText.hidden = false;
        btnLoading.hidden = true;
        submitBtn.disabled = false;
    }
});

// ============================================================================
// URS Generation
// ============================================================================

async function generateURS(skipClarification = false) {
    try {
        showToast('Generating URS...', 'info');
        
        const response = await fetch(`${API_BASE}/generate-urs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.sessionId,
                urs_id: state.ursId,
                skip_clarification: skipClarification
            })
        });
        
        if (!response.ok) throw new Error('Failed to generate URS');
        
        const result = await response.json();
        state.urs = result.urs;
        
        // Run QA review
        await runQAReview();
        
        // Render URS
        renderURS();
        
        showToast('URS generated successfully!', 'success');
        switchView('review');
        
    } catch (error) {
        console.error('Error generating URS:', error);
        showToast('Failed to generate URS.', 'error');
    }
}

async function runQAReview() {
    try {
        const response = await fetch(`${API_BASE}/review`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urs_id: state.ursId })
        });
        
        if (!response.ok) throw new Error('QA review failed');
        
        state.qaReport = await response.json();
        // QA scores display removed - could add back if needed
        
    } catch (error) {
        console.error('Error running QA:', error);
    }
}

function renderIssues() {
    if (!state.qaReport || !state.qaReport.issues || !elements.issuesList) {
        return;
    }
    
    elements.issuesList.innerHTML = state.qaReport.issues.map(issue => `
        <li class="issue-item ${issue.severity}" onclick="highlightIssue('${issue.location}')">
            <span class="issue-category">${issue.category}</span>
            <span class="issue-description">${issue.description}</span>
        </li>
    `).join('');
}

function highlightIssue(location) {
    // TODO: Scroll to and highlight the affected requirement
    console.log('Highlighting:', location);
}

function renderURS() {
    if (!state.urs) {
        elements.ursContent.innerHTML = '<div class="empty-state">No URS generated yet.</div>';
        return;
    }
    
    const urs = state.urs;
    
    // Update header
    document.getElementById('urs-title').textContent = urs.metadata?.title || 'Untitled URS';
    document.getElementById('urs-id').textContent = urs.metadata?.id || 'N/A';
    
    // Build clean document-style HTML
    let html = '';
    
    // Executive Summary - includes requestor info
    if (urs.executive_summary || urs.problem_statement) {
        const problem = urs.problem_statement?.current_state || '';
        const desired = urs.problem_statement?.desired_state || '';
        const requestor = urs.metadata?.requestor?.name || 'Unknown';
        const department = urs.metadata?.department || 'Unknown';
        const submissionDate = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
        const requestorTitle = urs.metadata?.requestor?.title || '';
        html += `
            <section class="doc-section summary-section">
                <div class="summary-header">
                    <h2>Project Summary</h2>
                </div>
                <div class="summary-meta">
                    <div class="meta-item">
                        <span class="meta-label">Requested by</span>
                        <span class="meta-value">${requestor}${requestorTitle ? `, ${requestorTitle}` : ''}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">Department</span>
                        <span class="meta-value">${department}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">Submitted</span>
                        <span class="meta-value">${submissionDate}</span>
                    </div>
                </div>
                <div class="summary-content">
                    <div class="summary-block">
                        <h4>Current Situation</h4>
                        <p class="editable-field" contenteditable="true" data-field="problem_statement.current_state">${problem}</p>
                    </div>
                    <div class="summary-block goal-block">
                        <h4>Desired Outcome</h4>
                        <p class="editable-field" contenteditable="true" data-field="problem_statement.desired_state">${desired}</p>
                    </div>
            </div>
            </section>
        `;
    }
    
    // Group requirements by priority
    const reqs = urs.functional_requirements || [];
    const mustHave = reqs.filter(r => r.priority?.toLowerCase() === 'must');
    const shouldHave = reqs.filter(r => r.priority?.toLowerCase() === 'should');
    const couldHave = reqs.filter(r => r.priority?.toLowerCase() === 'could');
    
    // Must Have Section
        html += `
        <section class="doc-section">
            <div class="priority-header must-header">
                <div>
                    <h2>Critical Requirements</h2>
                    <p class="priority-subtitle">Must Have — Core functionality required for launch</p>
                </div>
            </div>
            <div class="requirements-list">
                ${mustHave.map((req, i) => renderRequirement(req, i, 'Must Have', reqs.indexOf(req))).join('')}
            </div>
            <button class="btn-add-requirement" data-priority="Must">+ Add Critical Requirement</button>
        </section>
        `;
    
    // Should Have Section
        html += `
        <section class="doc-section">
            <div class="priority-header should-header">
                <div>
                    <h2>Important Requirements</h2>
                    <p class="priority-subtitle">Should Have — High value, but system can function without initially</p>
                        </div>
                    </div>
            <div class="requirements-list">
                ${shouldHave.map((req, i) => renderRequirement(req, i, 'Should Have', reqs.indexOf(req))).join('')}
            </div>
            <button class="btn-add-requirement" data-priority="Should">+ Add Important Requirement</button>
        </section>
        `;
    
    // Could Have Section
        html += `
        <section class="doc-section">
            <div class="priority-header could-header">
                <div>
                    <h2>Enhancement Requirements</h2>
                    <p class="priority-subtitle">Could Have — Nice to have, improves usability but not required</p>
                </div>
            </div>
            <div class="requirements-list">
                ${couldHave.map((req, i) => renderRequirement(req, i, 'Could Have', reqs.indexOf(req))).join('')}
            </div>
            <button class="btn-add-requirement" data-priority="Could">+ Add Enhancement Requirement</button>
        </section>
        `;
    
    elements.ursContent.innerHTML = html;
    
    // Add edit handlers
    document.querySelectorAll('[contenteditable="true"]').forEach(el => {
        el.addEventListener('blur', handleFieldEdit);
        el.addEventListener('keydown', (e) => {
            // For list items (acceptance criteria), Enter saves and moves to next
            if (e.key === 'Enter' && el.tagName === 'LI') {
                e.preventDefault();
                el.blur();
                // Try to focus next sibling
                const nextLi = el.nextElementSibling;
                if (nextLi && nextLi.contentEditable === 'true') {
                    nextLi.focus();
                }
            }
            // For paragraph fields, allow Enter for new lines (don't prevent default)
            // Escape to cancel and blur
            if (e.key === 'Escape') {
                el.blur();
            }
        });
    });
    
    // Add delete requirement handlers
    document.querySelectorAll('.btn-delete-req').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const index = parseInt(btn.dataset.index);
            if (state.urs && state.urs.functional_requirements) {
                if (confirm('Are you sure you want to delete this requirement?')) {
                    state.urs.functional_requirements.splice(index, 1);
                    renderURS();
                    showToast('Requirement deleted', 'success');
                }
            }
        });
    });
    
    // Add requirement handlers
    document.querySelectorAll('.btn-add-requirement').forEach(btn => {
        btn.addEventListener('click', () => {
            const priority = btn.dataset.priority;
            if (state.urs) {
                if (!state.urs.functional_requirements) {
                    state.urs.functional_requirements = [];
                }
                const newReq = {
                    requirement_id: `NEW-${Date.now()}`,
                    priority: priority,
                    description: 'New requirement - click to edit',
                    acceptance_criteria: [{ criterion: 'Acceptance criterion - click to edit' }],
                    source_references: [{ is_assumption: true }],
                    confidence_level: 'low'
                };
                state.urs.functional_requirements.push(newReq);
                renderURS();
                showToast('Requirement added', 'success');
            }
        });
    });
    
    // Add criteria handlers
    document.querySelectorAll('.btn-add-criteria').forEach(btn => {
        btn.addEventListener('click', () => {
            const reqIndex = parseInt(btn.dataset.reqIndex);
            if (state.urs && state.urs.functional_requirements && state.urs.functional_requirements[reqIndex]) {
                if (!state.urs.functional_requirements[reqIndex].acceptance_criteria) {
                    state.urs.functional_requirements[reqIndex].acceptance_criteria = [];
                }
                state.urs.functional_requirements[reqIndex].acceptance_criteria.push({
                    criterion: 'New criterion - click to edit'
                });
                renderURS();
                showToast('Criterion added', 'success');
            }
        });
    });
    
    // Priority dropdown handlers
    document.querySelectorAll('.priority-select').forEach(select => {
        select.addEventListener('change', (e) => {
            const index = parseInt(select.dataset.index);
            const newPriority = e.target.value;
            if (state.urs && state.urs.functional_requirements && state.urs.functional_requirements[index]) {
                state.urs.functional_requirements[index].priority = newPriority;
                renderURS();
                showToast(`Moved to ${newPriority === 'Must' ? 'Critical' : newPriority === 'Should' ? 'Important' : 'Enhancement'} Requirements`, 'success');
            }
        });
    });
    
    // Move up/down handlers
    document.querySelectorAll('.btn-move-up').forEach(btn => {
        btn.addEventListener('click', () => {
            const index = parseInt(btn.dataset.index);
            moveRequirement(index, 'up');
        });
    });
    
    document.querySelectorAll('.btn-move-down').forEach(btn => {
        btn.addEventListener('click', () => {
            const index = parseInt(btn.dataset.index);
            moveRequirement(index, 'down');
        });
    });
    
    // Drag and drop handlers
    setupDragAndDrop();
}

function moveRequirement(index, direction) {
    if (!state.urs || !state.urs.functional_requirements) return;
    
    const reqs = state.urs.functional_requirements;
    const req = reqs[index];
    if (!req) return;
    
    // Get all requirements with same priority
    const samePriority = reqs.filter(r => r.priority?.toLowerCase() === req.priority?.toLowerCase());
    const posInPriority = samePriority.indexOf(req);
    
    if (direction === 'up' && posInPriority > 0) {
        // Find the previous requirement with same priority
        const prevReq = samePriority[posInPriority - 1];
        const prevIndex = reqs.indexOf(prevReq);
        // Swap them
        [reqs[index], reqs[prevIndex]] = [reqs[prevIndex], reqs[index]];
        renderURS();
    } else if (direction === 'down' && posInPriority < samePriority.length - 1) {
        // Find the next requirement with same priority
        const nextReq = samePriority[posInPriority + 1];
        const nextIndex = reqs.indexOf(nextReq);
        // Swap them
        [reqs[index], reqs[nextIndex]] = [reqs[nextIndex], reqs[index]];
        renderURS();
    }
}

function setupDragAndDrop() {
    const requirementItems = document.querySelectorAll('.requirement-item[draggable="true"]');
    const requirementsLists = document.querySelectorAll('.requirements-list');
    
    let draggedItem = null;
    let draggedIndex = null;
    
    requirementItems.forEach(item => {
        item.addEventListener('dragstart', (e) => {
            draggedItem = item;
            draggedIndex = parseInt(item.dataset.index);
            item.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', draggedIndex);
        });
        
        item.addEventListener('dragend', () => {
            item.classList.remove('dragging');
            document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
            draggedItem = null;
            draggedIndex = null;
        });
        
        item.addEventListener('dragover', (e) => {
            e.preventDefault();
            if (draggedItem && draggedItem !== item) {
                item.classList.add('drag-over');
            }
        });
        
        item.addEventListener('dragleave', () => {
            item.classList.remove('drag-over');
        });
        
        item.addEventListener('drop', (e) => {
            e.preventDefault();
            item.classList.remove('drag-over');
            
            if (!draggedItem || draggedItem === item) return;
            
            const targetIndex = parseInt(item.dataset.index);
            const targetPriority = item.dataset.priority;
            
            if (state.urs && state.urs.functional_requirements) {
                const reqs = state.urs.functional_requirements;
                const movedReq = reqs[draggedIndex];
                
                // Update priority if dropped on different priority section
                if (movedReq.priority !== targetPriority) {
                    movedReq.priority = targetPriority;
                }
                
                // Remove from old position and insert at new position
                reqs.splice(draggedIndex, 1);
                const newTargetIndex = targetIndex > draggedIndex ? targetIndex - 1 : targetIndex;
                reqs.splice(newTargetIndex, 0, movedReq);
                
                renderURS();
                showToast('Requirement moved', 'success');
            }
        });
    });
    
    // Allow dropping on empty sections
    requirementsLists.forEach(list => {
        list.addEventListener('dragover', (e) => {
            e.preventDefault();
            if (draggedItem && list.children.length === 0) {
                list.classList.add('drag-over');
            }
        });
        
        list.addEventListener('dragleave', () => {
            list.classList.remove('drag-over');
        });
        
        list.addEventListener('drop', (e) => {
            e.preventDefault();
            list.classList.remove('drag-over');
            
            // Determine priority from section
            const section = list.closest('.doc-section');
            const header = section?.querySelector('.priority-header');
            let newPriority = 'Must';
            if (header?.classList.contains('should-header')) newPriority = 'Should';
            else if (header?.classList.contains('could-header')) newPriority = 'Could';
            
            if (draggedItem && state.urs && state.urs.functional_requirements) {
                const reqs = state.urs.functional_requirements;
                const movedReq = reqs[draggedIndex];
                movedReq.priority = newPriority;
                
                renderURS();
                showToast(`Moved to ${newPriority === 'Must' ? 'Critical' : newPriority === 'Should' ? 'Important' : 'Enhancement'} Requirements`, 'success');
            }
        });
    });
}

function renderRequirement(req, priorityIndex, priorityLabel, globalIndex) {
    const isAssumption = req.source_references?.some(r => r.is_assumption);
    // Use abbreviated IDs: CR = Critical, IR = Important, ER = Enhancement
    const prefixMap = {
        'Must Have': 'CR',
        'Should Have': 'IR', 
        'Could Have': 'ER'
    };
    const prefix = prefixMap[priorityLabel] || 'REQ';
    const reqId = `${prefix}${priorityIndex + 1}`;
    const currentPriority = req.priority?.toLowerCase() || 'must';
    
    return `
        <div class="requirement-item" id="req-${globalIndex}" draggable="true" data-index="${globalIndex}" data-priority="${req.priority}">
            <div class="requirement-header-row">
                <span class="drag-handle" title="Drag to reorder">⋮⋮</span>
                <span class="req-number">${reqId}</span>
                ${isAssumption ? '<span class="assumption-tag">Assumption</span>' : ''}
                <div class="requirement-controls">
                    <select class="priority-select" data-index="${globalIndex}" title="Change priority">
                        <option value="Must" ${currentPriority === 'must' ? 'selected' : ''}>Critical</option>
                        <option value="Should" ${currentPriority === 'should' ? 'selected' : ''}>Important</option>
                        <option value="Could" ${currentPriority === 'could' ? 'selected' : ''}>Enhancement</option>
                    </select>
                    <button class="btn-icon btn-move-up" data-index="${globalIndex}" title="Move up">↑</button>
                    <button class="btn-icon btn-move-down" data-index="${globalIndex}" title="Move down">↓</button>
                    <button class="btn-icon btn-delete btn-delete-req" data-index="${globalIndex}" title="Delete requirement">×</button>
                </div>
            </div>
            <p class="req-description editable-field" contenteditable="true" data-field="functional_requirements.${globalIndex}.description">${req.description}</p>
            <div class="acceptance-section">
                <span class="acceptance-label">Acceptance Criteria</span>
                <ul class="acceptance-list">
                    ${(req.acceptance_criteria || []).map((ac, j) => {
                        // Strip any leading bullets from criterion text
                        const cleanCriterion = (ac.criterion || '').replace(/^[\•\-\*\→\▪\◦\·\u2022\u2023\u25E6\u2043\u2219]\s*/g, '').trim();
                        return `<li class="editable-field" contenteditable="true" data-field="functional_requirements.${globalIndex}.acceptance_criteria.${j}.criterion">${cleanCriterion}</li>`;
                    }).join('')}
            </ul>
                <button class="btn-add-criteria" data-req-index="${globalIndex}">+ Add Criterion</button>
            </div>
        </div>
    `;
}

function handleFieldEdit(e) {
    const field = e.target.dataset.field;
    const value = e.target.innerText.trim();
    
    if (field && state.urs) {
        // Update the state
        setNestedValue(state.urs, field, value);
        showToast('Changes saved', 'success');
    }
}

function setNestedValue(obj, path, value) {
    const keys = path.split('.');
    let current = obj;
    
    for (let i = 0; i < keys.length - 1; i++) {
        const key = isNaN(keys[i]) ? keys[i] : parseInt(keys[i]);
        if (current[key] === undefined) return;
        current = current[key];
    }
    
    const lastKey = isNaN(keys[keys.length - 1]) ? keys[keys.length - 1] : parseInt(keys[keys.length - 1]);
    
    // Handle special case for pain_points which are objects
    if (path.includes('pain_points') && typeof current[lastKey] === 'object') {
        current[lastKey].description = value;
    } else {
        current[lastKey] = value;
    }
}

// ============================================================================
// Export & Actions
// ============================================================================

document.getElementById('btn-regenerate').addEventListener('click', () => {
    if (confirm('Regenerate the URS? This will create a new version.')) {
        generateURS();
    }
});

// Export as PDF
document.getElementById('btn-export-pdf').addEventListener('click', () => {
    if (!state.urs) {
        showToast('No URS to export', 'error');
        return;
    }
    
    // Create a printable version
    const printWindow = window.open('', '_blank');
    const urs = state.urs;
    
    printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>${urs.metadata?.title || 'User Requirements Specification'}</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 40px; color: #333; }
                h1 { color: #1a1a1a; border-bottom: 3px solid #c9a227; padding-bottom: 10px; }
                h2 { color: #a88620; margin-top: 30px; }
                h3 { color: #555; }
                .header { display: flex; justify-content: space-between; margin-bottom: 30px; }
                .logo { font-weight: bold; font-style: italic; }
                .logo span { color: #a88620; }
                .meta { color: #666; font-size: 0.9em; }
                .requirement { background: #f9f9f9; border-left: 4px solid #c9a227; padding: 15px; margin: 15px 0; }
                .req-id { font-weight: bold; color: #a88620; }
                .priority { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; margin-left: 10px; }
                .priority.must { background: #fee2e2; color: #dc2626; }
                .priority.should { background: #fef3c7; color: #d97706; }
                .priority.could { background: #dbeafe; color: #2563eb; }
                .criteria { margin-left: 20px; }
                .criteria li { margin: 5px 0; }
                .assumption { background: #fef3c7; color: #92400e; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; }
                .footer { margin-top: 50px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 0.9em; }
                @media print { body { padding: 20px; } }
            </style>
        </head>
        <body>
            <div class="header">
                <div class="logo">ECLIPSE <span>AUTOMATION</span></div>
                <div class="meta">
                    <div><strong>Document ID:</strong> ${urs.metadata?.id || state.ursId}</div>
                    <div><strong>Generated:</strong> ${new Date().toLocaleDateString()}</div>
                </div>
            </div>
            
            <h1>${urs.metadata?.title || 'User Requirements Specification'}</h1>
            
            ${urs.executive_summary ? `
                <h2>Executive Summary</h2>
                <p>${urs.executive_summary.summary || ''}</p>
                ${urs.executive_summary.business_value ? `<p><strong>Business Value:</strong> ${urs.executive_summary.business_value}</p>` : ''}
            ` : ''}
            
            ${urs.problem_statement ? `
                <h2>Problem Statement</h2>
                <h3>Current State</h3>
                <p>${urs.problem_statement.current_state || ''}</p>
                ${urs.problem_statement.pain_points?.length ? `
                    <h3>Pain Points</h3>
                    <ul>${urs.problem_statement.pain_points.map(p => `<li>${p.description}</li>`).join('')}</ul>
                ` : ''}
                <h3>Desired State</h3>
                <p>${urs.problem_statement.desired_state || ''}</p>
            ` : ''}
            
            ${urs.functional_requirements?.length ? `
                <h2>Functional Requirements</h2>
                ${urs.functional_requirements.map(req => `
                    <div class="requirement">
                        <span class="req-id">${req.requirement_id}</span>
                        <span class="priority ${(req.priority || '').toLowerCase()}">${req.priority}</span>
                        <p>${req.description}</p>
                        ${req.acceptance_criteria?.length ? `
                            <strong>Acceptance Criteria:</strong>
                            <ul class="criteria">
                                ${req.acceptance_criteria.map(ac => `<li>${ac.criterion}</li>`).join('')}
                            </ul>
                        ` : ''}
                        ${req.source_references?.some(r => r.is_assumption) ? '<span class="assumption">⚠️ Contains Assumptions</span>' : ''}
                    </div>
                `).join('')}
            ` : ''}
            
            ${urs.non_functional_requirements?.length ? `
                <h2>Non-Functional Requirements</h2>
                ${urs.non_functional_requirements.map(req => `
                    <div class="requirement">
                        <span class="req-id">${req.requirement_id}</span>
                        <span class="priority ${(req.priority || '').toLowerCase()}">${req.priority}</span>
                        <p>${req.description}</p>
                    </div>
                `).join('')}
            ` : ''}
            
            <div class="footer">
                <p>Generated by Eclipse Automation URS Generator</p>
                <p>This document requires review by the Digital Transformation team before implementation.</p>
            </div>
        </body>
        </html>
    `);
    
    printWindow.document.close();
    
    // Trigger print dialog after content loads
    printWindow.onload = () => {
        printWindow.print();
    };
    
    showToast('PDF export opened in new window. Use Print → Save as PDF', 'success');
});

// Export as Word Document (using RTF format - universally compatible)
document.getElementById('btn-export-word').addEventListener('click', async () => {
    if (!state.urs) {
        showToast('No URS to export', 'error');
        return;
    }
    
    const urs = state.urs;
    const title = urs.metadata?.title || 'User Requirements Specification';
    const ursId = urs.metadata?.id || state.ursId;
    const requestor = urs.metadata?.requestor?.name || 'Unknown';
    const requestorTitle = urs.metadata?.requestor?.title || '';
    const department = urs.metadata?.department || 'Unknown';
    const dateStr = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
    
    // Group requirements by priority
    const reqs = urs.functional_requirements || [];
    const mustHave = reqs.filter(r => r.priority?.toLowerCase() === 'must');
    const shouldHave = reqs.filter(r => r.priority?.toLowerCase() === 'should');
    const couldHave = reqs.filter(r => r.priority?.toLowerCase() === 'could');
    
    // Helper to escape HTML
    const escapeHtml = (text) => {
        if (!text) return '';
        return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                   .replace(/\n/g, '<br/>');
    };
    const cleanCriterion = (text) => escapeHtml((text || '').replace(/^[\•\-\*\→\▪\◦\·\u2022\u2023\u25E6\u2043\u2219]\s*/g, '').trim());
    
    // Build requirements HTML
    const renderReqHtml = (req, id) => {
        const isAssumption = req.source_references?.some(r => r.is_assumption);
        let html = `<p style="margin-top:12pt;"><b style="color:#8B7320;">${id}:</b> ${escapeHtml(req.description)}`;
        if (isAssumption) {
            html += `<i style="color:#dc3545;"> [Assumption]</i>`;
        }
        html += `</p>`;
        
        if (req.acceptance_criteria?.length > 0) {
            html += `<p style="margin-left:20pt;margin-top:6pt;"><b>Acceptance Criteria:</b></p><ul style="margin-left:40pt;">`;
            req.acceptance_criteria.forEach(ac => {
                html += `<li>${cleanCriterion(ac.criterion)}</li>`;
            });
            html += `</ul>`;
        }
        return html;
    };
    
    let requirementsHtml = '';
    
    if (mustHave.length > 0) {
        requirementsHtml += `<h2 style="color:#8B7320;margin-top:24pt;">Critical Requirements (Must Have)</h2>`;
        requirementsHtml += `<p style="font-style:italic;color:#666;">Core functionality required for launch</p>`;
        mustHave.forEach((req, i) => { requirementsHtml += renderReqHtml(req, `CR${i + 1}`); });
    }
    
    if (shouldHave.length > 0) {
        requirementsHtml += `<h2 style="color:#8B7320;margin-top:24pt;">Important Requirements (Should Have)</h2>`;
        requirementsHtml += `<p style="font-style:italic;color:#666;">High value, but system can function without initially</p>`;
        shouldHave.forEach((req, i) => { requirementsHtml += renderReqHtml(req, `IR${i + 1}`); });
    }
    
    if (couldHave.length > 0) {
        requirementsHtml += `<h2 style="color:#8B7320;margin-top:24pt;">Enhancement Requirements (Could Have)</h2>`;
        requirementsHtml += `<p style="font-style:italic;color:#666;">Nice to have, improves usability but not required</p>`;
        couldHave.forEach((req, i) => { requirementsHtml += renderReqHtml(req, `ER${i + 1}`); });
    }
    
    // Word-compatible HTML document
    const wordContent = `<!DOCTYPE html>
<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">
<head>
<meta charset="utf-8">
<title>${escapeHtml(title)}</title>
<!--[if gte mso 9]>
<xml>
<w:WordDocument>
<w:View>Print</w:View>
<w:Zoom>100</w:Zoom>
</w:WordDocument>
</xml>
<![endif]-->
<style>
@page { size: 8.5in 11in; margin: 1in; }
body { font-family: Calibri, Arial, sans-serif; font-size: 11pt; line-height: 1.4; color: #1a1a1a; }
h1 { font-size: 24pt; color: #1a1a1a; margin-bottom: 12pt; border-bottom: 2px solid #8B7320; padding-bottom: 8pt; }
h2 { font-size: 14pt; color: #8B7320; margin-top: 18pt; margin-bottom: 6pt; }
h3 { font-size: 12pt; color: #333; margin-top: 12pt; }
table { border-collapse: collapse; margin: 12pt 0; }
td { padding: 6pt 12pt; border: 1px solid #ddd; }
td:first-child { font-weight: bold; background: #f8f8f8; width: 140pt; }
ul { margin-top: 6pt; }
li { margin-bottom: 4pt; }
.header { text-align: right; font-size: 10pt; color: #666; margin-bottom: 24pt; }
.footer { text-align: center; font-size: 9pt; color: #666; margin-top: 36pt; border-top: 1px solid #ddd; padding-top: 12pt; }
</style>
</head>
<body>
<div class="header">
<b>ECLIPSE AUTOMATION</b><br/>
User Requirements Specification<br/>
Document ID: ${escapeHtml(ursId)}
</div>

<h1>${escapeHtml(title)}</h1>

<table>
<tr><td>Requested by</td><td>${escapeHtml(requestor)}${requestorTitle ? ', ' + escapeHtml(requestorTitle) : ''}</td></tr>
<tr><td>Department</td><td>${escapeHtml(department)}</td></tr>
<tr><td>Date</td><td>${escapeHtml(dateStr)}</td></tr>
<tr><td>Status</td><td>Draft</td></tr>
</table>

<h2>Executive Summary</h2>
<h3>Current Situation</h3>
<p>${escapeHtml(urs.problem_statement?.current_state || 'No description provided.')}</p>
<h3>Desired Outcome</h3>
<p>${escapeHtml(urs.problem_statement?.desired_state || 'Not specified.')}</p>

${requirementsHtml}

<div class="footer">
Generated by Eclipse Automation URS Generator<br/>
This document requires review by the Digital Transformation team before implementation.
</div>
</body>
</html>`;
    
    // Create and download as .doc file
    const safeTitle = title.replace(/[^a-z0-9\s]/gi, '').replace(/\s+/g, '_').substring(0, 40);
    const filename = `${ursId}_${safeTitle}.doc`;
    
    // Create blob and use msSaveBlob for IE/Edge or create object URL for others
    const blob = new Blob(['\ufeff' + wordContent], { type: 'application/msword' });
    
    // Check for IE/Edge msSaveBlob
    if (window.navigator && window.navigator.msSaveOrOpenBlob) {
        window.navigator.msSaveOrOpenBlob(blob, filename);
    } else {
        // For modern browsers, create a hidden link and click it
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        link.style.position = 'absolute';
        link.style.left = '-9999px';
        document.body.appendChild(link);
        
        // Use setTimeout to ensure the link is in the DOM
        setTimeout(() => {
            link.click();
            setTimeout(() => {
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
            }, 100);
        }, 0);
    }
    
    console.log('Word Download triggered:', filename);
    showToast('Downloading: ' + filename, 'success');
});

// Send to Digital Transformation
document.getElementById('btn-send-email').addEventListener('click', () => {
    if (!state.urs) {
        showToast('No URS to send', 'error');
        return;
    }
    
    const urs = state.urs;
    const title = urs.metadata?.title || 'User Requirements Specification';
    const ursId = urs.metadata?.id || state.ursId;
    const requestorName = urs.metadata?.requestor?.name || 'Not specified';
    const department = urs.metadata?.department || 'Not specified';
    
    // First, trigger both exports
    showToast('Preparing documents... Please save both PDF and Word exports.', 'info');
    
    // Trigger PDF export
    document.getElementById('btn-export-pdf').click();
    
    // Trigger Word export after a brief delay
    setTimeout(() => {
        document.getElementById('btn-export-word').click();
    }, 1000);
    
    // Build email body
    const body = `Hi Digital Transformation Team,

A new User Requirements Specification has been submitted for review.

** PLEASE ATTACH THE PDF AND WORD DOCUMENTS YOU JUST DOWNLOADED **

Document Details:
━━━━━━━━━━━━━━━━━━━━━━
• Title: ${title}
• Document ID: ${ursId}
• Requested by: ${requestorName}
• Department: ${department}
• Submitted: ${new Date().toLocaleDateString()}

Summary:
${urs.problem_statement?.current_state || 'See attached document for details.'}

Goal:
${urs.problem_statement?.desired_state || 'See attached document for details.'}

Requirements Count:
• Critical (Must Have): ${(urs.functional_requirements || []).filter(r => r.priority?.toLowerCase() === 'must').length}
• Important (Should Have): ${(urs.functional_requirements || []).filter(r => r.priority?.toLowerCase() === 'should').length}
• Enhancement (Could Have): ${(urs.functional_requirements || []).filter(r => r.priority?.toLowerCase() === 'could').length}

Please review the attached documents and provide feedback.

Best regards,
${requestorName}
${department}`;

    const subject = `[URS Submission] ${title} (${ursId}) - ${department}`;
    const email = 'jacky.a.chen@eclipseautomation.com';
    
    // Open email client after exports
    setTimeout(() => {
        const mailtoLink = `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
        window.location.href = mailtoLink;
        showToast('Email client opened - Remember to attach the downloaded documents!', 'success');
    }, 2500);
});

// ============================================================================
// Utilities
// ============================================================================

function updateSessionStatus(active) {
    elements.sessionStatus.textContent = active ? `Session: ${state.ursId}` : 'No Active Session';
    elements.sessionStatus.classList.toggle('active', active);
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    elements.toastContainer.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ============================================================================
// Issue Filters
// ============================================================================

document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const severity = btn.dataset.severity;
        
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        document.querySelectorAll('.issue-item').forEach(item => {
            if (severity === 'all' || item.classList.contains(severity)) {
                item.style.display = '';
            } else {
                item.style.display = 'none';
            }
        });
    });
});

// ============================================================================
// Initialize
// ============================================================================

console.log('URS Generator initialized');

