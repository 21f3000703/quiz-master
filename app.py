from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from flask_login import LoginManager, login_user, UserMixin, login_required, logout_user, current_user
from datetime import datetime
import matplotlib.pyplot as plt
import io
import base64
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import abort

# Initialize Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quiz_master.db'
app.secret_key = 'supersecretkey'
# Initialize Database
db = SQLAlchemy(app)
db_session = db.session
login_manager = LoginManager(app)
login_manager.login_view = 'user_login'

# Models

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100))
    qualification = db.Column(db.String(100))
    dob = db.Column(db.Date)
    role = db.Column(db.String(20), default='user')  # 'user' or 'admin'

    def __repr__(self):
        return f'<User {self.username}>'

@login_manager.user_loader
def load_user(user_id):
    return db_session.get(User, int(user_id))

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)

class Chapter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'))

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    date = db.Column(db.Date, nullable=False)
    duration = db.Column(db.Time, nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapter.id'))


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    correct_option = db.Column(db.String(200), nullable=False)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'))
    
class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    time_stamp_of_attempt = db.Column(db.DateTime)
    total_scored = db.Column(db.Integer)

def initialize_database():
    with app.app_context():
        if not os.path.exists('quiz_master.db'):
            db.create_all()
        
        # Check if the admin user already exists
        existing_admin = User.query.filter_by(username='aastha').first()
        if not existing_admin:
            # Use 'pbkdf2:sha256' hashing method
            hashed_password = generate_password_hash('12345', method='pbkdf2:sha256')
            admin = User(username='aastha', password=hashed_password, full_name='Quiz Master', role='admin')
            db.session.add(admin)
            db.session.commit()
        else:
            print("Admin account already exists. Skipping admin creation.")

@app.route('/')
def landing_page():
    return render_template('landing.html')

# Admin Login Route
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Authenticate admin user
        admin = User.query.filter_by(username=username, role='admin').first()
        if admin and check_password_hash(admin.password, password):
            login_user(admin)  # Use Flask-Login to handle the session
            flash('Admin logged in successfully.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials', 'danger')

    return render_template('admin_login.html')

# User Login Route
@app.route('/login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username, role='user').first()
        # print(f"User found: {user} with pass: {user.password}")
        if user and check_password_hash(user.password, password):
            print(f"User found successfully")
            login_user(user)
            return redirect(url_for('user_dashboard'))
        else:
            print(f"Wrong password or user name")
            flash('Invalid user credentials', 'danger')

    return render_template('user_login.html')

# User Registration Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        full_name = request.form['full_name']
        qualification = request.form['qualification']
        dob = request.form['dob']

        try:
            date_obj = datetime.strptime(dob, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'danger')
            return render_template('register.html')

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
        else:
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            user = User(
                username=username,
                password=hashed_password,
                full_name=full_name,
                qualification=qualification,
                dob=date_obj,
                role='user'
            )
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('user_login'))
    
    return render_template('register.html')

@app.route('/user_dashboard')
@login_required
def user_dashboard():
    user_id = current_user.id

    quizzes = Quiz.query.all()
    past_scores = Score.query.filter_by(user_id=user_id).all()

    # Prepare data for summary chart
    quiz_titles = []
    scores = []
    for score in past_scores:
        quiz = Quiz.query.get(score.quiz_id)
        quiz_titles.append(quiz.title)
        scores.append(score.total_scored)

    return render_template(
        'user_dashboard.html',
        user=current_user,
        quizzes=quizzes,
        past_scores=past_scores,
        quiz_titles=quiz_titles,
        scores=scores
    )
# Route to start a quiz
@app.route('/attempt_quiz/<int:quiz_id>', methods=['GET', 'POST'])
def attempt_quiz(quiz_id):
    if 'user' not in session:
        return redirect(url_for('user_login'))
    
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = Question.query.filter_by(quiz_id=quiz_id).all()
    
    if request.method == 'POST':
        total_score = 0
        for question in questions:
            user_answer = request.form.get(str(question.id))
            if user_answer == question.correct_option:
                total_score += 1

        # Save the score
        score = Score(
            quiz_id=quiz.id,
            user_id=session['user'],
            time_stamp_of_attempt=datetime.now(),
            total_scored=total_score
        )
        db.session.add(score)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('An error occurred while recording the score.', 'danger')

        flash(f'Quiz Completed! You scored {total_score}/{len(questions)}.', 'success')
        return redirect(url_for('user_dashboard'))

    return render_template('attempt_quiz.html', quiz=quiz, questions=questions)


# Route to view quiz history
@app.route('/quiz_history')
def quiz_history():
    if 'user' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user']
    scores = Score.query.filter_by(user_id=user_id).all()
    return render_template('quiz_history.html', scores=scores)

# Admin Dashboard Route
@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    search_query = request.args.get('search')
    users = []
    subjects = []
    quizzes = []

    if search_query:
        users = User.query.filter(or_(
            User.username.like(f"%{search_query}%"),
            User.full_name.like(f"%{search_query}%"),
            User.qualification.like(f"%{search_query}%")
        )).all()

        subjects = Subject.query.filter(Subject.name.like(f"%{search_query}%")).all()

        quizzes = Quiz.query.filter(Quiz.title.like(f"%{search_query}%")).all()

    return render_template('admin_dashboard.html', users=users, subjects=subjects, quizzes=quizzes, search_query=search_query)

@app.route('/admin_dashboard/summary')
def summary_dashboard():
    quiz_attempts = db.session.query(Quiz.title, db.func.count(Score.id)).join(Score).group_by(Quiz.id).all()
    
    quiz_titles = [quiz[0] for quiz in quiz_attempts]
    attempt_counts = [quiz[1] for quiz in quiz_attempts]

    fig, ax = plt.subplots()
    ax.bar(quiz_titles, attempt_counts)

    ax.set_xlabel('Quizzes')
    ax.set_ylabel('Number of Attempts')
    ax.set_title('Quiz Attempts Summary')

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    img_data = base64.b64encode(img.read()).decode('utf-8')

    return render_template('admin_dashboard_summary.html', img_data=img_data)

# Route to manage users
@app.route('/manage_users')
def manage_users():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    users = User.query.filter_by(role='user').all()  # Show only user accounts
    return render_template('manage_users.html', users=users)

# Route to delete a user
@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    user = User.query.get_or_404(user_id)
    
    # Ensure admin users cannot be deleted
    if user.role == 'admin':
        flash('Cannot delete admin users.', 'danger')
        return redirect(url_for('manage_users'))

    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.username} has been deleted.', 'success')
    return redirect(url_for('manage_users'))

# Manage Subjects Route with Chapter Management Links
@app.route('/manage_subjects')
def manage_subjects():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    subjects = Subject.query.all()
    return render_template('manage_subjects.html', subjects=subjects)


# Add Subject Route
@app.route('/add_subject', methods=['GET', 'POST'])
@login_required
def add_subject():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')

        if not name:
            flash('Subject name is required.', 'danger')
            return redirect(url_for('add_subject'))

        # Check if the subject already exists
        if Subject.query.filter_by(name=name).first():
            flash('Subject with this name already exists.', 'danger')
            return redirect(url_for('add_subject'))

        new_subject = Subject(name=name, description=description)
        db.session.add(new_subject)
        db.session.commit()
        flash('Subject added successfully!', 'success')
        return redirect(url_for('manage_subjects'))

    return render_template('add_subject.html')

# Edit Subject Route
@app.route('/edit_subject/<int:subject_id>', methods=['GET', 'POST'])
@login_required
def edit_subject(subject_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
        
    subject = Subject.query.get_or_404(subject_id)
    
    if request.method == 'POST':
        subject.name = request.form.get('name')
        subject.description = request.form.get('description')

        db.session.commit()
        flash('Subject updated successfully!', 'success')
        return redirect(url_for('manage_subjects'))

    return render_template('edit_subject.html', subject=subject)

# Delete Subject Route
@app.route('/delete_subject/<int:subject_id>')
@login_required
def delete_subject(subject_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    subject = Subject.query.get_or_404(subject_id)
    db.session.delete(subject)
    db.session.commit()
    flash('Subject deleted successfully!', 'success')
    return redirect(url_for('manage_subjects'))


# View and Manage Chapters for a Specific Subject
@app.route('/manage_chapters/<int:subject_id>')
def manage_chapters(subject_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    subject = Subject.query.get_or_404(subject_id)
    chapters = Chapter.query.filter_by(subject_id=subject_id).all()
    return render_template('manage_chapters.html', subject=subject, chapters=chapters)


# Add Chapter Route
@app.route('/add_chapter/<int:subject_id>', methods=['GET', 'POST'])
def add_chapter(subject_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')

        new_chapter = Chapter(name=name, description=description, subject_id=subject_id)
        db.session.add(new_chapter)
        db.session.commit()
        flash('Chapter added successfully!', 'success')
        return redirect(url_for('manage_chapters', subject_id=subject_id))

    return render_template('add_chapter.html', subject_id=subject_id)


# Edit Chapter Route
@app.route('/edit_chapter/<int:chapter_id>', methods=['GET', 'POST'])
def edit_chapter(chapter_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    chapter = Chapter.query.get_or_404(chapter_id)

    if request.method == 'POST':
        chapter.name = request.form.get('name')
        chapter.description = request.form.get('description')
        db.session.commit()
        flash('Chapter updated successfully!', 'success')
        return redirect(url_for('manage_chapters', subject_id=chapter.subject_id))

    return render_template('edit_chapter.html', chapter=chapter)


# Delete Chapter Route
@app.route('/delete_chapter/<int:chapter_id>', methods=['GET'])
def delete_chapter(chapter_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    chapter = Chapter.query.get_or_404(chapter_id)
    subject_id = chapter.subject_id
    db.session.delete(chapter)
    db.session.commit()
    flash('Chapter deleted successfully!', 'success')
    return redirect(url_for('manage_chapters', subject_id=subject_id))

@app.route('/manage_quizzes/<int:chapter_id>')
def manage_quizzes(chapter_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    chapter = Chapter.query.get_or_404(chapter_id)
    quizzes = Quiz.query.filter_by(chapter_id=chapter_id).all()
    return render_template('manage_quizzes.html', chapter=chapter, quizzes=quizzes)


@app.route('/add_quiz/<int:chapter_id>', methods=['GET', 'POST'])
def add_quiz(chapter_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    chapter = Chapter.query.get_or_404(chapter_id)

    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description')
        
        # Convert string to date object
        date_str = request.form['date']
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Convert string to time object
        duration_str = request.form['duration']
        duration_obj = datetime.strptime(duration_str, '%H:%M').time()

        new_quiz = Quiz(
            title=title,
            description=description,
            date=date_obj,
            duration=duration_obj,
            chapter_id=chapter.id
        )
        db.session.add(new_quiz)
        db.session.commit()

        flash('Quiz added successfully', 'success')
        return redirect(url_for('manage_quizzes', chapter_id=chapter.id))

    return render_template('add_quiz.html', chapter=chapter)

# Edit Quiz
@app.route('/edit_quiz/<int:quiz_id>', methods=['GET', 'POST'])
def edit_quiz(quiz_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    quiz = Quiz.query.get_or_404(quiz_id)

    if request.method == 'POST':
        quiz.title = request.form['title']
        quiz.description = request.form['description']
        quiz.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        quiz.duration = datetime.strptime(request.form['duration'], '%H:%M').time()

        db.session.commit()
        flash('Quiz updated successfully!', 'success')
        return redirect(url_for('manage_quizzes', chapter_id=quiz.chapter_id))

    return render_template('edit_quiz.html', quiz=quiz)


# Delete Quiz
@app.route('/delete_quiz/<int:quiz_id>')
def delete_quiz(quiz_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    quiz = Quiz.query.get_or_404(quiz_id)
    chapter_id = quiz.chapter_id
    db.session.delete(quiz)
    db.session.commit()
    flash('Quiz deleted successfully!', 'success')
    return redirect(url_for('manage_quizzes', chapter_id=chapter_id))
@app.route('/manage_questions/<int:quiz_id>')
def manage_questions(quiz_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
        
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = Question.query.filter_by(quiz_id=quiz.id).all()
    return render_template('manage_questions.html', quiz=quiz, questions=questions)

@app.route('/add_question/<int:quiz_id>', methods=['GET', 'POST'])
def add_question(quiz_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    quiz = Quiz.query.get_or_404(quiz_id)

    if request.method == 'POST':
        text = request.form['text']
        option_a = request.form['option_a']
        option_b = request.form['option_b']
        option_c = request.form['option_c']
        option_d = request.form['option_d']
        correct_option = request.form['correct_option']

        if correct_option not in [option_a, option_b, option_c, option_d]:
            flash('Correct option must match one of the provided options.', 'danger')
            return redirect(url_for('add_question', quiz_id=quiz.id))

        question = Question(
            text=text,
            option_a=option_a,
            option_b=option_b,
            option_c=option_c,
            option_d=option_d,
            correct_option=correct_option,
            quiz_id=quiz.id
        )
        db.session.add(question)
        db.session.commit()
        flash('Question added successfully!', 'success')
        return redirect(url_for('manage_questions', quiz_id=quiz.id))

    return render_template('add_question.html', quiz=quiz)

@app.route('/edit_question/<int:question_id>', methods=['GET', 'POST'])
def edit_question(question_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    question = Question.query.get_or_404(question_id)

    if request.method == 'POST':
        question.text = request.form['text']
        question.option_a = request.form['option_a']
        question.option_b = request.form['option_b']
        question.option_c = request.form['option_c']
        question.option_d = request.form['option_d']
        correct_option = request.form['correct_option']

        if correct_option not in [question.option_a, question.option_b, question.option_c, question.option_d]:
            flash('Correct option must match one of the provided options.', 'danger')
            return redirect(url_for('edit_question', question_id=question.id))

        question.correct_option = correct_option
        db.session.commit()
        flash('Question updated successfully!', 'success')
        return redirect(url_for('manage_questions', quiz_id=question.quiz_id))

    return render_template('edit_question.html', question=question)

@app.route('/delete_question/<int:question_id>')
def delete_question(question_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    question = Question.query.get_or_404(question_id)
    db.session.delete(question)
    db.session.commit()
    flash('Question deleted successfully!', 'success')
    return redirect(url_for('manage_questions', quiz_id=question.quiz_id))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for('user_login'))

if __name__ == '__main__':
    initialize_database()
    app.run(debug=True)
