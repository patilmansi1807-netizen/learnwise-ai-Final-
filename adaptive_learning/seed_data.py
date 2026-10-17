import json

def seed_database(db, models):
    User = models['User']
    Subject = models['Subject']
    Concept = models['Concept']
    Prerequisite = models['Prerequisite']
    Question = models['Question']
    StudentMastery = models['StudentMastery']

    if db.session.query(User).first():
        return  # Database already seeded

    # 1. Users
    student = User(username="Aarav Sharma", role="student", selected_subject="Mathematics", daily_goal_mins=30)
    teacher = User(username="Prof. Rao", role="teacher", selected_subject="Mathematics")
    db.session.add_all([student, teacher])
    db.session.commit()

    # 2. Subjects
    subjects = [
        Subject(name="Mathematics", description="Foundations, Pre-Algebra, and Geometry"),
        Subject(name="Computer Science", description="Logic, Algorithms, and Code Construction"),
        Subject(name="Science", description="Physics, Chemistry, and Biological Systems"),
        Subject(name="English", description="Grammar, Critical Reading, and Rhetoric")
    ]
    db.session.add_all(subjects)

    # 3. Concepts with Prerequisite Structure
    concepts = [
        Concept(subject_name="Mathematics", code="MATH_ARITH", title="Basic Arithmetic", description="Addition, subtraction, and order of operations.", tier=1, p_init=0.85),
        Concept(subject_name="Mathematics", code="MATH_FRAC", title="Fractions & Decimals", description="Equal division, equivalent ratios, and denominators.", tier=2, p_init=0.35),
        Concept(subject_name="Mathematics", code="MATH_ALG1", title="Linear Equations", description="Solving single-variable linear equations.", tier=3, p_init=0.20),
        Concept(subject_name="Mathematics", code="MATH_QUAD", title="Quadratic Expressions", description="Factoring polynomials and roots.", tier=4, p_init=0.10),

        Concept(subject_name="Computer Science", code="CS_VAR", title="Variables & Types", description="Data containers, numbers, strings, and booleans.", tier=1, p_init=0.80),
        Concept(subject_name="Computer Science", code="CS_COND", title="Conditional Logic", description="If, else if, and boolean operators.", tier=2, p_init=0.40),
        Concept(subject_name="Computer Science", code="CS_LOOP", title="Loops & Iteration", description="For loops, while loops, and iterators.", tier=3, p_init=0.15),
    ]
    db.session.add_all(concepts)
    db.session.commit()

    # 4. Prerequisites
    prereqs = [
        Prerequisite(concept_code="MATH_FRAC", prereq_code="MATH_ARITH"),
        Prerequisite(concept_code="MATH_ALG1", prereq_code="MATH_FRAC"),
        Prerequisite(concept_code="MATH_QUAD", prereq_code="MATH_ALG1"),
        Prerequisite(concept_code="CS_COND", prereq_code="CS_VAR"),
        Prerequisite(concept_code="CS_LOOP", prereq_code="CS_COND"),
    ]
    db.session.add_all(prereqs)

    # 5. Diagnostic & Adaptive Questions
    questions = [
        Question(
            concept_code="MATH_FRAC",
            difficulty=0.3,
            text="What is the result of 1/4 + 2/4?",
            option_a="3/8",
            option_b="3/4",
            option_c="2/16",
            option_d="1/2",
            correct_option="B",
            explanation="When denominators are identical, add the numerators directly: 1 + 2 = 3. The denominator remains 4.",
            distractor_reasons=json.dumps({"A": "Added denominators directly together (4+4=8).", "C": "Multiplied denominators erroneously."})
        ),
        Question(
            concept_code="MATH_FRAC",
            difficulty=0.6,
            text="Simplify: 2/3 + 1/6",
            option_a="3/9",
            option_b="5/6",
            option_c="3/6",
            option_d="4/6",
            correct_option="B",
            explanation="Convert 2/3 to equivalent fraction with base 6: (2*2)/(3*2) = 4/6. Then 4/6 + 1/6 = 5/6.",
            distractor_reasons=json.dumps({"A": "Added numerators and denominators straight across (2+1)/(3+6)."})
        ),
        Question(
            concept_code="MATH_ALG1",
            difficulty=0.4,
            text="Solve for x: 2x + 4 = 12",
            option_a="x = 8",
            option_b="x = 4",
            option_c="x = 6",
            option_d="x = 16",
            correct_option="B",
            explanation="Subtract 4 from both sides: 2x = 8. Then divide both sides by 2: x = 4.",
            distractor_reasons=json.dumps({"A": "Subtracted 4 but forgot to divide by 2.", "C": "Divided 12 by 2 before subtracting 4."})
        ),
        Question(
            concept_code="CS_COND",
            difficulty=0.4,
            text="What does this evaluate to? (True and False) or (not False)",
            option_a="True",
            option_b="False",
            option_c="None",
            option_d="SyntaxError",
            correct_option="A",
            explanation="(True and False) evaluates to False. (not False) evaluates to True. False or True yields True.",
            distractor_reasons=json.dumps({"B": "Believed 'and False' poisoned the entire boolean expression."})
        )
    ]
    db.session.add_all(questions)

    # 6. Seed Initial Mastery
    db.session.add_all([
        StudentMastery(user_id=student.id, concept_code="MATH_ARITH", p_know=0.88),
        StudentMastery(user_id=student.id, concept_code="MATH_FRAC", p_know=0.45),
        StudentMastery(user_id=student.id, concept_code="MATH_ALG1", p_know=0.25),
        StudentMastery(user_id=student.id, concept_code="CS_VAR", p_know=0.82),
        StudentMastery(user_id=student.id, concept_code="CS_COND", p_know=0.38)
    ])

    db.session.commit()
