document.addEventListener("DOMContentLoaded", () => {
    // 1. Adaptive Quiz Submission Flow
    const quizForm = document.getElementById("quiz-form");
    if (quizForm) {
        let startTime = Date.now();
        quizForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const selected = document.querySelector('input[name="opt"]:checked');
            if (!selected) {
                alert("Please select an answer choice before submitting.");
                return;
            }

            const timeTaken = Math.round((Date.now() - startTime) / 1000);
            const questionId = document.getElementById("question-id").value;

            document.getElementById("btn-submit").disabled = true;

            try {
                const res = await fetch("/api/submit-answer", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        question_id: questionId,
                        selected_option: selected.value,
                        time_taken: timeTaken
                    })
                });

                const data = await res.json();
                renderFeedback(data);
            } catch (err) {
                console.error("Submission failed:", err);
                alert("Error recording answer. Please retry.");
                document.getElementById("btn-submit").disabled = false;
            }
        });
    }

    // 2. Interactive Concept Map Connection Renderer
    const edgeLayer = document.getElementById("edge-layer");
    if (edgeLayer && window.GRAPH_EDGES) {
        drawConceptGraphEdges();
        window.addEventListener("resize", drawConceptGraphEdges);
    }

    // 3. Code Sandbox Execution
    const runBtn = document.getElementById("btn-run-code");
    if (runBtn) {
        runBtn.addEventListener("click", async () => {
            const code = document.getElementById("code-editor").value;
            const outputBox = document.getElementById("code-output");
            outputBox.textContent = "Executing in isolated sub-process...";

            try {
                const res = await fetch("/api/run-code", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ code: code, test_call: "solution(10)" })
                });
                const data = await res.json();
                if (data.success) {
                    outputBox.textContent = `Success!\nOutput of solution(10): ${data.output}`;
                    outputBox.style.color = "#3fb950";
                } else {
                    outputBox.textContent = `Runtime Failure:\n${data.error}`;
                    outputBox.style.color = "#f85149";
                }
            } catch (err) {
                outputBox.textContent = `Server communication failure: ${err.message}`;
            }
        });
    }
});

function renderFeedback(data) {
    const feedbackPanel = document.getElementById("feedback-panel");
    const alertBox = document.getElementById("feedback-alert");
    const misBox = document.getElementById("misconception-box");
    const misText = document.getElementById("misconception-text");
    const expText = document.getElementById("explanation-text");
    const shiftText = document.getElementById("shift-text");
    const liveMastery = document.getElementById("live-mastery");

    feedbackPanel.classList.remove("hidden");

    if (data.is_correct) {
        alertBox.className = "alert alert-correct";
        alertBox.textContent = "Correct! Well reasoned.";
        misBox.classList.add("hidden");
    } else {
        alertBox.className = "alert alert-incorrect";
        alertBox.textContent = `Incorrect. The accurate answer was option (${data.correct_option}).`;
        if (data.misconception) {
            misText.textContent = data.misconception;
            misBox.classList.remove("hidden");
        } else {
            misBox.classList.add("hidden");
        }
    }

    expText.textContent = data.explanation;
    shiftText.textContent = `${data.p_before}% → ${data.p_after}%`;
    liveMastery.textContent = `${data.p_after}%`;
}

async function askTutor(mode) {
    const conceptCode = document.getElementById("concept-code").value;
    const respBox = document.getElementById("tutor-response");
    const content = document.getElementById("tutor-content");
    const title = document.getElementById("tutor-mode-title");

    respBox.classList.remove("hidden");
    content.textContent = "Consulting pedagogical knowledge graph...";

    try {
        const res = await fetch("/api/ai-tutor-explain", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ concept_code: conceptCode, type: mode })
        });
        const data = await res.json();
        title.textContent = mode.replace("_", " ").toUpperCase();
        content.textContent = data.content;
    } catch (err) {
        content.textContent = "Unable to retrieve explanation. Please proceed with standard practice.";
    }
}

function drawConceptGraphEdges() {
    const svg = document.getElementById("edge-layer");
    const container = document.getElementById("graph-container");
    const cRect = container.getBoundingClientRect();
    svg.innerHTML = "";

    window.GRAPH_EDGES.forEach(edge => {
        const fromEl = document.getElementById(`node-${edge.from}`);
        const toEl = document.getElementById(`node-${edge.to}`);
        if (!fromEl || !toEl) return;

        const fRect = fromEl.getBoundingClientRect();
        const tRect = toEl.getBoundingClientRect();

        const x1 = fRect.right - cRect.left;
        const y1 = fRect.top + fRect.height / 2 - cRect.top;
        const x2 = tRect.left - cRect.left;
        const y2 = tRect.top + tRect.height / 2 - cRect.top;

        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        const dx = (x2 - x1) / 2;
        const d = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;

        path.setAttribute("d", d);
        path.setAttribute("stroke", "#30363d");
        path.setAttribute("stroke-width", "2");
        path.setAttribute("fill", "none");
        svg.appendChild(path);
    });
}