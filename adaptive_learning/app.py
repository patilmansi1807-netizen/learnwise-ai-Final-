import os
import json
import time
import ast
import multiprocessing
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = 'adaptive-learning-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///adaptive_learning.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ----------------- Database Models ----------------- #

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    role = db.Column(db.String(20), default='student')  # 'student' or 'teacher'
    selected_subject = db.Column(db.String(50), default='Mathematics')
    daily_goal_mins = db.Column(db.Integer, default=30)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))

class Concept(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject_name = db.Column(db.String(80), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    # BKT Default Parameters
    p_init = db.Column(db.Float, default=0.2)     # L0: initial knowledge
    p_transit = db.Column(db.Float, default=0.15) # T: probability of learning
    p_slip = db.Column(db.Float, default=0.1)      # S: slip probability
    p_guess = db.Column(db.Float, default=0.2)     # G: guess probability
    tier = db.Column(db.Integer, default=1)        # Level in hierarchy

class Prerequisite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    concept_code = db.Column(db.String(50), nullable=False)
    prereq_code = db.Column(db.String(50), nullable=False)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    concept_code = db.Column(db.String(50), nullable=False)
    text = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.Float, default=0.5) # 0.1 (easy) to 0.9 (hard)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False) # 'A', 'B', 'C', 'D'
    explanation = db.Column(db.Text, nullable=False)
    distractor_reasons = db.Column(db.Text) # JSON string mapping option to misconception

class StudentMastery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    concept_code = db.Column(db.String(50), nullable=False)
    p_know = db.Column(db.Float, default=0.2) # Current estimated p(L_t)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

class LearningAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    selected_option = db.Column(db.String(1), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    p_know_before = db.Column(db.Float, nullable=False)
    p_know_after = db.Column(db.Float, nullable=False)
    time_taken_seconds = db.Column(db.Integer, default=15)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


# ----------------- BKT Core Engine ----------------- #

def update_bkt(p_prev, is_correct, p_transit=0.15, p_slip=0.1, p_guess=0.2):
    """
    Standard Bayesian Knowledge Tracing update:
    P(L_t | action) -> Posterior
    P(L_{t+1}) = Posterior + (1 - Posterior) * P(T)
    """
    if is_correct:
        numerator = p_prev * (1.0 - p_slip)
        denominator = (p_prev * (1.0 - p_slip)) + ((1.0 - p_prev) * p_guess)
    else:
        numerator = p_prev * p_slip
        denominator = (p_prev * p_slip) + ((1.0 - p_prev) * (1.0 - p_guess))
    
    p_posterior = numerator / denominator if denominator > 0 else p_prev
    p_next = p_posterior + (1.0 - p_posterior) * p_transit
    return round(min(max(p_next, 0.01), 0.99), 4)

def check_prerequisites_met(user_id, concept_code, threshold=0.65):
    """Verifies that all prerequisite concepts have achieved the minimum mastery threshold."""
    prereqs = Prerequisite.query.filter_by(concept_code=concept_code).all()
    for req in prereqs:
        m = StudentMastery.query.filter_by(user_id=user_id, concept_code=req.prereq_code).first()
        if not m or m.p_know < threshold:
            prereq_concept = Concept.query.filter_by(code=req.prereq_code).first()
            return False, prereq_concept.title if prereq_concept else req.prereq_code
    return True, None

def get_recommended_concept(user_id, subject_name):
    """
    Determines next concept based on:
    1. Unfulfilled prerequisites.
    2. In-progress concepts (0.2 < mastery < 0.75).
    3. Unstarted concepts whose prerequisites are fulfilled.
    """
    concepts = Concept.query.filter_by(subject_name=subject_name).order_by(Concept.tier.asc()).all()
    
    for c in concepts:
        m = StudentMastery.query.filter_by(user_id=user_id, concept_code=c.code).first()
        p = m.p_know if m else c.p_init
        if p < 0.75:
            prereqs_ok, missing = check_prerequisites_met(user_id, c.code)
            if prereqs_ok:
                return c, f"Focus here: current mastery is {int(p*100)}% and prerequisites are met."
            else:
                missing_c = Concept.query.filter_by(title=missing).first()
                if missing_c:
                    return missing_c, f"Prerequisite gap: master '{missing}' first before '{c.title}'."
    
    return concepts[0] if concepts else None, "Review or expand your mastery."


# ----------------- Safe Python Code Sandbox ----------------- #

def _sandbox_worker(code_str, test_call_str, queue):
    """Restricted execution worker running in an isolated process."""
    forbidden_nodes = (ast.Import, ast.ImportFrom, ast.Delete, ast.Global, ast.Nonlocal)
    try:
        parsed = ast.parse(code_str)
        for node in ast.walk(parsed):
            if isinstance(node, forbidden_nodes):
                queue.put({"success": False, "error": f"Security restriction: '{type(node).__name__}' is disabled in safe mode."})
                return
            if isinstance(node, ast.Name) and node.id in ['open', 'eval', 'exec', '__import__', 'compile']:
                queue.put({"success": False, "error": f"Security restriction: function '{node.id}' is blocked."})
                return

        safe_builtins = {
            'range': range, 'len': len, 'sum': sum, 'min': min, 'max': max,
            'abs': abs, 'int': int, 'float': float, 'str': str, 'list': list,
            'dict': dict, 'set': set, 'bool': bool, 'enumerate': enumerate
        }
        loc = {}
        exec(code_str, {"__builtins__": safe_builtins}, loc)
        eval_result = eval(test_call_str, {"__builtins__": safe_builtins}, loc)
        queue.put({"success": True, "output": str(eval_result)})
    except Exception as e:
        queue.put({"success": False, "error": f"{type(e).__name__}: {str(e)}"})

def execute_safe_python(code_str, test_call_str, timeout_seconds=2):
    try:
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        proc = ctx.Process(target=_sandbox_worker, args=(code_str, test_call_str, q))
        proc.start()
        proc.join(timeout_seconds)
        if proc.is_alive():
            proc.terminate()
            proc.join()
            return {"success": False, "error": "Execution timed out (Max 2 seconds permitted)."}
        if not q.empty():
            return q.get()
        return {"success": False, "error": "Execution failed without response."}
    except Exception as err:
        return {"success": False, "error": f"Sandbox supervisor error: {str(err)}"}


# ----------------- Context & Auth Helpers ----------------- #

@app.before_request
def establish_identity():
    if 'user_id' not in session:
        student = User.query.filter_by(role='student').first()
        if student:
            session['user_id'] = student.id
            session['role'] = student.role

def get_current_user():
    user_id = session.get('user_id', 1)
    return db.session.get(User, user_id)


# ----------------- Web Routes ----------------- #

@app.route('/')
def index():
    return redirect(url_for('student_dashboard'))

@app.route('/dashboard')
def student_dashboard():
    user = get_current_user()
    if not user:
        return "System initializing. Please reload.", 503

    subjects = Subject.query.all()
    active_subject = request.args.get('subject', user.selected_subject)
    
    concepts = Concept.query.filter_by(subject_name=active_subject).order_by(Concept.tier).all()
    concept_stats = []
    mastered_count = 0
    struggling_count = 0

    for c in concepts:
        m = StudentMastery.query.filter_by(user_id=user.id, concept_code=c.code).first()
        p = m.p_know if m else c.p_init
        status = 'Mastered' if p >= 0.75 else ('In Progress' if p >= 0.4 else 'Needs Attention')
        if p >= 0.75: 
            mastered_count += 1
        if p < 0.4: 
            struggling_count += 1
        
        prereqs_ok, missing = check_prerequisites_met(user.id, c.code)
        concept_stats.append({
            'code': c.code,
            'title': c.title,
            'mastery_pct': int(p * 100),
            'status': status,
            'prereqs_met': prereqs_ok,
            'missing_prereq': missing
        })

    rec_concept, rec_reason = get_recommended_concept(user.id, active_subject)
    
    attempts = LearningAttempt.query.filter_by(user_id=user.id).order_by(LearningAttempt.timestamp.desc()).limit(8).all()
    total_attempts = LearningAttempt.query.filter_by(user_id=user.id).count()
    correct_attempts = LearningAttempt.query.filter_by(user_id=user.id, is_correct=True).count()
    overall_accuracy = int((correct_attempts / total_attempts * 100)) if total_attempts > 0 else 0

    return render_template(
        'student_dashboard.html',
        user=user,
        subjects=subjects,
        active_subject=active_subject,
        concepts=concept_stats,
        rec_concept=rec_concept,
        rec_reason=rec_reason,
        mastered_count=mastered_count,
        struggling_count=struggling_count,
        overall_accuracy=overall_accuracy,
        total_attempts=total_attempts,
        recent_attempts=attempts
    )

@app.route('/switch-subject', methods=['POST'])
def switch_subject():
    user = get_current_user()
    sub = request.form.get('subject')
    if user and sub:
        user.selected_subject = sub
        db.session.commit()
    return redirect(url_for('student_dashboard', subject=sub))

@app.route('/practice')
def practice():
    user = get_current_user()
    concept_code = request.args.get('concept_code')
    
    if not concept_code:
        rec_concept, _ = get_recommended_concept(user.id, user.selected_subject)
        concept_code = rec_concept.code if rec_concept else 'MATH_FRAC'

    concept = Concept.query.filter_by(code=concept_code).first_or_404()
    mastery_record = StudentMastery.query.filter_by(user_id=user.id, concept_code=concept_code).first()
    p_current = mastery_record.p_know if mastery_record else concept.p_init

    all_qs = Question.query.filter_by(concept_code=concept_code).all()
    if not all_qs:
        return "No questions populated for this concept.", 404
        
    all_qs.sort(key=lambda q: abs(q.difficulty - p_current))
    question = all_qs[0]

    return render_template('practice.html', user=user, concept=concept, question=question, mastery_pct=int(p_current * 100))

@app.route('/api/submit-answer', methods=['POST'])
def submit_answer():
    user = get_current_user()
    data = request.json or {}
    q_id = data.get('question_id')
    selected_opt = data.get('selected_option', '').upper()
    time_taken = data.get('time_taken', 12)

    question = db.session.get(Question, q_id)
    if not question:
        return jsonify({'error': 'Question not found'}), 404

    concept = Concept.query.filter_by(code=question.concept_code).first()
    mastery = StudentMastery.query.filter_by(user_id=user.id, concept_code=concept.code).first()
    
    if not mastery:
        mastery = StudentMastery(user_id=user.id, concept_code=concept.code, p_know=concept.p_init)
        db.session.add(mastery)

    p_before = mastery.p_know
    is_correct = (selected_opt == question.correct_option)
    p_after = update_bkt(p_before, is_correct, concept.p_transit, concept.p_slip, concept.p_guess)
    mastery.p_know = p_after
    mastery.last_updated = datetime.utcnow()

    attempt = LearningAttempt(
        user_id=user.id,
        question_id=question.id,
        selected_option=selected_opt,
        is_correct=is_correct,
        p_know_before=p_before,
        p_know_after=p_after,
        time_taken_seconds=time_taken
    )
    db.session.add(attempt)
    db.session.commit()

    misconception = None
    if not is_correct and question.distractor_reasons:
        try:
            reasons = json.loads(question.distractor_reasons)
            misconception = reasons.get(selected_opt)
        except Exception:
            misconception = "Common pitfall associated with this operation."

    return jsonify({
        'is_correct': is_correct,
        'correct_option': question.correct_option,
        'explanation': question.explanation,
        'misconception': misconception,
        'p_before': round(p_before * 100, 1),
        'p_after': round(p_after * 100, 1),
        'concept_code': concept.code
    })

@app.route('/api/ai-tutor-explain', methods=['POST'])
def ai_tutor_explain():
    data = request.json or {}
    concept_code = data.get('concept_code')
    query_type = data.get('type', 'hint')
    
    concept = Concept.query.filter_by(code=concept_code).first()
    if not concept:
        return jsonify({"error": "Concept not found"}), 404

    explanations = {
        'MATH_FRAC': {
            'hint': "Look at the denominator: it defines how many equal slices make one whole unit. Don't add denominators directly!",
            'real_life': "Think of a pizza sliced into 8 equal parts. 3 slices is 3/8. If you combine it with 2/8, you count the slices: 5/8 total.",
            'step_by_step': "Step 1: Find a common denominator. Step 2: Scale numerators accordingly. Step 3: Add only numerators. Step 4: Simplify."
        },
        'MATH_ALG1': {
            'hint': "Whatever arithmetic operation you apply to the left-hand side, apply the exact same to the right-hand side to maintain balance.",
            'real_life': "A balanced seesaw: if you remove 5kg from one side, you must remove 5kg from the other side to keep it level.",
            'step_by_step': "Step 1: Group variable terms on one side. Step 2: Combine constants on the opposite side. Step 3: Divide by coefficient."
        },
        'CS_COND': {
            'hint': "Conditionals evaluate to either True or False. If the first 'if' branch triggers, subsequent 'elif' branches are skipped.",
            'real_life': "A traffic light: IF it is green, you proceed; ELSE IF it is amber, you brake; ELSE, you stop.",
            'step_by_step': "Step 1: Check boolean condition. Step 2: Execute indented block if True. Step 3: Exit block structure."
        }
    }

    lib = explanations.get(concept.code, {
        'hint': f"Focus on foundational properties of {concept.title}.",
        'real_life': f"Relate {concept.title} to daily balance and resource allocation.",
        'step_by_step': "Identify known quantities -> Map the relation -> Evaluate incrementally."
    })

    return jsonify({
        "mode": query_type,
        "content": lib.get(query_type, lib['hint']),
        "concept": concept.title
    })

@app.route('/concept-map')
def concept_map():
    user = get_current_user()
    active_subject = request.args.get('subject', user.selected_subject)
    concepts = Concept.query.filter_by(subject_name=active_subject).all()
    prereqs = Prerequisite.query.all()
    masteries = {m.concept_code: m.p_know for m in StudentMastery.query.filter_by(user_id=user.id).all()}

    nodes = []
    for c in concepts:
        p = masteries.get(c.code, c.p_init)
        status = 'mastered' if p >= 0.75 else ('in_progress' if p >= 0.4 else 'needs_attention')
        nodes.append({
            'id': c.code,
            'label': c.title,
            'tier': c.tier,
            'mastery': int(p * 100),
            'status': status
        })

    edges = []
    for pr in prereqs:
        if any(n['id'] == pr.concept_code for n in nodes) and any(n['id'] == pr.prereq_code for n in nodes):
            edges.append({'from': pr.prereq_code, 'to': pr.concept_code})

    return render_template('concept_map.html', nodes=nodes, edges=edges, active_subject=active_subject)

@app.route('/code-lab')
def code_lab():
    return render_template('code_lab.html')

@app.route('/api/run-code', methods=['POST'])
def run_code():
    data = request.json or {}
    code_text = data.get('code', '')
    test_call = data.get('test_call', 'solution(5)')
    result = execute_safe_python(code_text, test_call)
    return jsonify(result)

@app.route('/session-replay')
def session_replay():
    user = get_current_user()
    attempts = LearningAttempt.query.filter_by(user_id=user.id).order_by(LearningAttempt.timestamp.asc()).all()
    history = []
    for a in attempts:
        q = db.session.get(Question, a.question_id)
        c = Concept.query.filter_by(code=q.concept_code).first() if q else None
        history.append({
            'time': a.timestamp.strftime("%H:%M:%S"),
            'concept': c.title if c else "Unknown",
            'is_correct': a.is_correct,
            'p_before': int(a.p_know_before * 100),
            'p_after': int(a.p_know_after * 100),
            'delta': int((a.p_know_after - a.p_know_before) * 100),
            'time_taken': a.time_taken_seconds
        })
    return render_template('replay.html', history=history)

@app.route('/teacher')
def teacher_dashboard():
    students = User.query.filter_by(role='student').all()
    all_concepts = Concept.query.all()
    
    struggling_topics = []
    for c in all_concepts:
        masteries = StudentMastery.query.filter_by(concept_code=c.code).all()
        if masteries:
            avg_p = sum(m.p_know for m in masteries) / len(masteries)
            if avg_p < 0.6:
                struggling_topics.append({
                    'code': c.code,
                    'title': c.title,
                    'subject': c.subject_name,
                    'avg_mastery': int(avg_p * 100),
                    'student_count': len(masteries)
                })

    student_summaries = []
    for s in students:
        attempts = LearningAttempt.query.filter_by(user_id=s.id).all()
        total = len(attempts)
        correct = len([a for a in attempts if a.is_correct])
        student_summaries.append({
            'id': s.id,
            'name': s.username,
            'subject': s.selected_subject,
            'total_attempts': total,
            'accuracy': int(correct / total * 100) if total > 0 else 0,
            'needs_intervention': (total > 3 and (correct / total) < 0.5)
        })

    return render_template(
        'teacher_dashboard.html',
        students=student_summaries,
        struggling_topics=struggling_topics
    )


# ----------------- DB Initialization & Seeding ----------------- #

if __name__ == '__main__':
    from seed_data import seed_database
    with app.app_context():
        db.create_all()
        models = {
            'User': User,
            'Subject': Subject,
            'Concept': Concept,
            'Prerequisite': Prerequisite,
            'Question': Question,
            'StudentMastery': StudentMastery,
            'LearningAttempt': LearningAttempt
        }
        seed_database(db, models)
    app.run(debug=True, port=5000)