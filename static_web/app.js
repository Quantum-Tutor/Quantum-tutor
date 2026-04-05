const chatContainer = document.getElementById('chat-container');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');

let conversationHistory = [];
const LEARNING_STATE_KEY = 'quantum_learning_state';

function formatRetryHint(seconds) {
    const value = Number(seconds || 0);
    if (!value || value <= 0) return "Retry: normal";
    if (value < 60) return `Retry: ~${value.toFixed(1)}s`;
    const minutes = Math.floor(value / 60);
    const remainder = Math.round(value % 60);
    return `Retry: ~${minutes}m ${remainder}s`;
}

function getLearningStudentId() {
    let studentId = localStorage.getItem('quantum_learning_student_id');
    if (!studentId) {
        studentId = `web-${Math.random().toString(36).slice(2, 10)}`;
        localStorage.setItem('quantum_learning_student_id', studentId);
    }
    return studentId;
}

function saveLearningState(state) {
    localStorage.setItem(LEARNING_STATE_KEY, JSON.stringify(state || {}));
}

function loadLearningState() {
    const saved = localStorage.getItem(LEARNING_STATE_KEY);
    if (!saved) return {};
    try {
        return JSON.parse(saved);
    } catch (error) {
        return {};
    }
}

function updateLearningSidebarFromRoute(route) {
    const nextNode = route.next_node || {};
    const milestones = route.milestones || [];
    const activeMilestone = milestones.find(item => !item.unlocked) || milestones[0] || {};
    const badges = ((route.gamification || {}).badges || []).length;
    const points = ((route.gamification || {}).points || 0);
    const currentLevel = route.current_level || 'exploracion';
    const diagnosticCompleted = Boolean(route.diagnostic_completed);

    document.getElementById('learning-level').textContent = `Nivel: ${currentLevel}`;
    document.getElementById('learning-points').textContent = `Puntos: ${points}`;
    document.getElementById('learning-next-node').textContent = `Siguiente nodo: ${nextNode.title || 'pendiente'}`;
    document.getElementById('learning-next-milestone').textContent = `Milestone: ${activeMilestone.label || 'pendiente'}`;
    document.getElementById('learning-badges').textContent = `Badges: ${badges}`;
    document.getElementById('learning-diagnostic-btn').textContent = diagnosticCompleted
        ? 'Repetir diagnostico'
        : 'Iniciar diagnostico';

    saveLearningState({
        level: currentLevel,
        points,
        nextNode: nextNode.title || 'pendiente',
        nextMilestone: activeMilestone.label || 'pendiente',
        badges,
        diagnosticCompleted
    });
}

async function refreshLearningJourney() {
    try {
        const studentId = getLearningStudentId();
        const res = await fetch(`/api/ruta-personalizada?student_id=${encodeURIComponent(studentId)}`);
        if (!res.ok) return;
        const route = await res.json();
        updateLearningSidebarFromRoute(route);
    } catch (error) {
        console.error('Learning route unavailable', error);
    }
}

window.onload = () => {
    loadHistory();
    const savedLearning = loadLearningState();
    if (savedLearning.level) document.getElementById('learning-level').textContent = `Nivel: ${savedLearning.level}`;
    if (savedLearning.points !== undefined) document.getElementById('learning-points').textContent = `Puntos: ${savedLearning.points}`;
    if (savedLearning.nextNode) document.getElementById('learning-next-node').textContent = `Siguiente nodo: ${savedLearning.nextNode}`;
    if (savedLearning.nextMilestone) document.getElementById('learning-next-milestone').textContent = `Milestone: ${savedLearning.nextMilestone}`;
    if (savedLearning.badges !== undefined) document.getElementById('learning-badges').textContent = `Badges: ${savedLearning.badges}`;
    if (savedLearning.diagnosticCompleted) {
        document.getElementById('learning-diagnostic-btn').textContent = 'Repetir diagnostico';
    }
    refreshLearningJourney();
    chatInput.focus();
};

function saveHistory() {
    localStorage.setItem('quantum_chat_history', JSON.stringify(conversationHistory));
}

function loadHistory() {
    const saved = localStorage.getItem('quantum_chat_history');
    if (saved) {
        conversationHistory = JSON.parse(saved);
        if (conversationHistory.length > 0) {
            // Limpiar si había pantalla de bienvenida
            const welcome = document.querySelector('.system-welcome');
            if (welcome) welcome.remove();
            
            conversationHistory.forEach(msg => {
                appendMessage(msg.role, msg.content, false, false); // false para no volver a guardar al cargar
            });

            // Restore Sidebar State from the last assistant message metadata if we had a structured way, 
            // but since we only save text, we should ideally have saved the state too.
            // For now, let's look at the last assistant message if it were stored with data.
            // Better approach: Save the state separately.
            const savedState = localStorage.getItem('quantum_sidebar_state');
            if (savedState) {
                const state = JSON.parse(savedState);
                if (state.omega) document.getElementById('omega-class').textContent = "OMEGA Class: " + state.omega;
                if (state.entropy) document.getElementById('entropy-metric').textContent = "Entropía: " + state.entropy;
                if (state.engine) document.getElementById('engine-status').textContent = "Engine: " + state.engine;
                if (state.retryHint) document.getElementById('retry-hint').textContent = state.retryHint;
            }
        }
    }
}

function clearDiagnosticCard() {
    const existing = document.getElementById('learning-diagnostic-card');
    if (existing) existing.remove();
}

function renderDiagnosticCard(payload) {
    clearDiagnosticCard();

    const card = document.createElement('div');
    card.className = 'diagnostic-card';
    card.id = 'learning-diagnostic-card';

    const questionsHtml = (payload.questions || []).map((question, index) => `
        <div class="diagnostic-question">
            <label for="diag-${question.id}">${index + 1}. ${question.prompt}</label>
            <select id="diag-${question.id}" data-question-id="${question.id}">
                <option value="">Selecciona una opcion</option>
                ${(question.options || []).map(option => `<option value="${option}">${option}</option>`).join('')}
            </select>
        </div>
    `).join('');

    card.innerHTML = `
        <h3>Diagnostico inicial adaptativo</h3>
        <p>Objetivo: ${payload.goal || 'fundamentos'} | Nivel objetivo: ${payload.target_level || 'beginner'} | Tiempo estimado: ${payload.estimated_minutes || 0} min</p>
        ${questionsHtml}
        <div class="diagnostic-actions">
            <button class="diagnostic-submit" onclick="submitLearningDiagnostic()">Evaluar diagnostico</button>
        </div>
    `;

    const welcome = document.querySelector('.system-welcome');
    if (welcome) {
        welcome.remove();
    }
    chatContainer.prepend(card);
}

async function startLearningDiagnostic() {
    try {
        const studentId = getLearningStudentId();
        const res = await fetch(`/api/diagnostico-inicial?student_id=${encodeURIComponent(studentId)}&max_questions=4`);
        if (!res.ok) {
            appendMessage('assistant', '**Diagnostico no disponible:** No pude obtener el bloque inicial ahora mismo.');
            return;
        }
        const payload = await res.json();
        renderDiagnosticCard(payload);
        chatContainer.scrollTop = 0;
    } catch (error) {
        appendMessage('assistant', '**Diagnostico no disponible:** Fallo de conectividad con el motor adaptativo.');
    }
}

async function submitLearningDiagnostic() {
    const card = document.getElementById('learning-diagnostic-card');
    if (!card) return;

    const selects = Array.from(card.querySelectorAll('select[data-question-id]'));
    const unanswered = selects.filter(select => !select.value);
    if (unanswered.length > 0) {
        appendMessage('assistant', '**Completa el diagnostico:** Aun hay preguntas sin responder.');
        return;
    }

    const studentId = getLearningStudentId();
    const feedback = [];

    for (const select of selects) {
        const questionId = select.dataset.questionId;
        const answer = select.value;
        const res = await fetch('/api/evaluar-respuesta', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                student_id: studentId,
                question_id: questionId,
                answer
            })
        });

        if (!res.ok) {
            appendMessage('assistant', '**Diagnostico incompleto:** Fallo al evaluar una de las respuestas.');
            return;
        }

        feedback.push(await res.json());
    }

    clearDiagnosticCard();

    const correctCount = feedback.filter(item => item.correcto).length;
    const remediationTitles = feedback
        .map(item => ((item.recommended_remediation || {}).title || '').trim())
        .filter(Boolean)
        .filter((value, index, arr) => arr.indexOf(value) === index);

    let summary = `**Diagnostico completado:** ${correctCount}/${feedback.length} respuestas correctas.`;
    if (remediationTitles.length > 0) {
        summary += `\n\nRefuerzo sugerido: ${remediationTitles.join(', ')}.`;
    }

    feedback.forEach((item, index) => {
        summary += `\n\n${index + 1}. ${item.correcto ? 'Correcta' : 'Para reforzar'}: ${item.feedback}`;
    });

    appendMessage('assistant', summary);
    await refreshLearningJourney();
}

function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
    if (textarea.value === '') {
        textarea.style.height = '24px'; // Reset for empty
    }
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
    document.getElementById('sidebar-overlay').classList.toggle('open');
}

function checkEnter(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

function startNewChat() {
    conversationHistory = [];
    localStorage.removeItem('quantum_chat_history');
    localStorage.removeItem('quantum_sidebar_state');
    clearDiagnosticCard();
    chatContainer.innerHTML = `
        <div class="system-welcome">
            <div class="logo-wrapper">⚛️</div>
            <h1>¿En qué te puedo ayudar hoy?</h1>
            <p>Soy tu instructor especializado en Mecánica Cuántica. Pregúntame sobre el Efecto Túnel, Osciladores Armónicos, o sube tu derivación matemática.</p>
        </div>
    `;
    document.getElementById('omega-class').textContent = "OMEGA Class: Indiferenciada";
    document.getElementById('entropy-metric').textContent = "Entropía: 0.00";
    document.getElementById('retry-hint').textContent = "Retry: normal";
    refreshLearningJourney();
}

function renderMath(element) {
    if (typeof renderMathInElement === "function") {
        renderMathInElement(element, {
            delimiters: [
                {left: "$$", right: "$$", display: true},
                {left: "\\[", right: "\\]", display: true},
                {left: "$", right: "$", display: false},
                {left: "\\(", right: "\\)", display: false}
            ],
            throwOnError: false
        });
    }
}

function appendMessage(role, content, isHtml = false, shouldSave = true) {
    // Remove welcome screen if exists
    const welcome = document.querySelector('.system-welcome');
    if (welcome) welcome.remove();

    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    
    let avatarChar = role === 'user' ? 'U' : '⚛️';
    
    let processedContent = content;
    if (!isHtml && typeof marked === "object") {
        const rawHtml = marked.parse(content);
        // SECURITY: sanitizar el HTML generado por marked para prevenir XSS.
        // DOMPurify elimina atributos y etiquetas peligrosas (onerror, <script>, etc.)
        processedContent = (typeof DOMPurify !== 'undefined')
            ? DOMPurify.sanitize(rawHtml, { USE_PROFILES: { html: true } })
            : rawHtml.replace(/<script[\s\S]*?<\/script>/gi, '');
    }
    
    const innerHtml = `
        <div class="message-inner">
            <div class="message-avatar">${avatarChar}</div>
            <div class="message-content">
                ${processedContent}
            </div>
        </div>
    `;
    msgDiv.innerHTML = innerHtml;
    chatContainer.appendChild(msgDiv);
    
    // Highlight Code Blocks & Add Copy Buttons
    msgDiv.querySelectorAll('pre').forEach(pre => {
        const codeBlock = pre.querySelector('code');
        if (codeBlock && typeof hljs !== 'undefined') {
            hljs.highlightElement(codeBlock);
        }
        
        // Add Copy Button
        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.textContent = 'Copy';
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(pre.innerText.replace('Copy', '').trim());
            copyBtn.textContent = 'Copied!';
            setTimeout(() => copyBtn.textContent = 'Copy', 2000);
        };
        pre.appendChild(copyBtn);
    });

    // Render LaTeX
    renderMath(msgDiv.querySelector('.message-content'));
    
    chatContainer.scrollTop = chatContainer.scrollHeight;
    
    if (shouldSave) saveHistory();
    
    return msgDiv;
}

async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    appendMessage('user', text);
    chatInput.value = '';
    autoResize(chatInput);
    
    sendBtn.disabled = true;
    chatInput.disabled = true;

    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message assistant loading-msg';
    loadingDiv.innerHTML = `
        <div class="message-inner">
            <div class="message-avatar">⚛️</div>
            <div class="message-content" style="color:#aaa;"><span class="loading"></span> Sincronizando núcleos cuánticos...</div>
        </div>
    `;
    chatContainer.appendChild(loadingDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    try {
        const payload = {
            message: text,
            history: conversationHistory,
            user_id: getLearningStudentId()
        };

        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        chatContainer.removeChild(loadingDiv);
        sendBtn.disabled = false;
        chatInput.disabled = false;
        chatInput.focus();

        if (res.ok) {
            const data = await res.json();
            const botResponse = data.response || "No context provided.";
            
            conversationHistory.push({role: "user", content: text});
            conversationHistory.push({role: "assistant", content: botResponse});
            
            appendMessage('assistant', botResponse);
            
            // Update Sidebar Analytics 
            let sidebarState = {};
            if (data.relational_data) {
                const omega = data.relational_data.omega_class || 'Indiferenciada';
                const entropy = data.relational_data.entropy ? data.relational_data.entropy.toFixed(2) : "0.00";
                document.getElementById('omega-class').textContent = "OMEGA Class: " + omega;
                document.getElementById('entropy-metric').textContent = "Entropía: " + entropy;
                sidebarState.omega = omega;
                sidebarState.entropy = entropy;
            }
            if (data.engine_status) {
                document.getElementById('engine-status').textContent = "Engine: " + data.engine_status;
                sidebarState.engine = data.engine_status;
            }
            const retrySource = (data.rate_limit && data.rate_limit.retry_after_seconds)
                || (data.backpressure && data.backpressure.retry_after_seconds)
                || (data.provider_retry && data.provider_retry.retry_after_seconds)
                || 0;
            const retryHint = formatRetryHint(retrySource);
            document.getElementById('retry-hint').textContent = retryHint;
            sidebarState.retryHint = retryHint;
            localStorage.setItem('quantum_sidebar_state', JSON.stringify(sidebarState));
            await refreshLearningJourney();
        } else {
            const err = await res.json();
            const retryAfter = Number(err.retry_after_seconds || res.headers.get('Retry-After') || 0);
            const retryHint = formatRetryHint(retryAfter);
            const engineState = err.error_code || 'ERROR';
            document.getElementById('engine-status').textContent = "Engine: " + engineState;
            document.getElementById('retry-hint').textContent = retryHint;
            localStorage.setItem('quantum_sidebar_state', JSON.stringify({
                engine: engineState,
                retryHint
            }));
            appendMessage(
                'assistant',
                `**${err.error_code || 'Error interno'}:** ${err.message || err.error || 'Fallo en el backend'}${retryAfter ? `\n\n${retryHint}` : ''}`
            );
        }

    } catch (e) {
        if(chatContainer.contains(loadingDiv)) chatContainer.removeChild(loadingDiv);
        sendBtn.disabled = false;
        chatInput.disabled = false;
        appendMessage('assistant', `**Error de conectividad:** Servidor inalcanzable.`);
    }
}

function triggerUpload() {
    document.getElementById('file-upload').click();
}

async function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    appendMessage('user', `*Subiendo derivación matemática para análisis visual: ${file.name}...*`);
    
    const formData = new FormData();
    formData.append("file", file);
    
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message assistant loading-msg';
    loadingDiv.innerHTML = `
        <div class="message-inner">
            <div class="message-avatar">⚛️</div>
            <div class="message-content" style="color:#aaa;"><span class="loading"></span> Analizando con Deep Vision Engine...</div>
        </div>
    `;
    chatContainer.appendChild(loadingDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    try {
        const res = await fetch('/api/vision', {
            method: 'POST',
            body: formData
        });
        
        chatContainer.removeChild(loadingDiv);
        document.getElementById('file-upload').value = ''; 
        
        if (res.ok) {
            const data = await res.json();
            const visionText = data.vision_prompt;
            
            // Preview Image in Chat
            const reader = new FileReader();
            reader.onload = (e) => {
                const img = document.createElement('img');
                img.src = e.target.result;
                img.className = 'image-preview-msg';
                // Find user message to append preview
                const userMsgs = document.querySelectorAll('.message.user');
                const lastUserMsg = userMsgs[userMsgs.length - 1].querySelector('.message-content');
                lastUserMsg.appendChild(img);
            };
            reader.readAsDataURL(file);

            chatInput.value = visionText;
            autoResize(chatInput);
            chatInput.focus();
            
            appendMessage('assistant', `Análisis visual completado. He inyectado los resultados en tu entrada de texto. Revísalos y envía el mensaje para recibir tutoría socrática.`);
        } else {
            appendMessage('assistant', `**Error Vision Engine:** Imposible extraer fórmulas.`);
        }
    } catch (e) {
        if(chatContainer.contains(loadingDiv)) chatContainer.removeChild(loadingDiv);
        appendMessage('assistant', `**Error de red:** Servidor de visión caído.`);
    }
}
