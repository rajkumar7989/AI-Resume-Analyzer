from flask import Flask, render_template, request, session, redirect, url_for
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import fitz
import os


# =========================================================
# LOAD ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()


# =========================================================
# FLASK APPLICATION
# =========================================================

app = Flask(__name__)

app.secret_key = os.getenv(
    "SECRET_KEY",
    "ai-resume-analyzer-secret-key"
)


# =========================================================
# MYSQL CONFIGURATION
# =========================================================

app.config["MYSQL_HOST"] = os.getenv(
    "MYSQL_HOST",
    "localhost"
)

app.config["MYSQL_USER"] = os.getenv(
    "MYSQL_USER",
    "root"
)

app.config["MYSQL_PASSWORD"] = os.getenv(
    "MYSQL_PASSWORD",
    ""
)

app.config["MYSQL_DB"] = os.getenv(
    "MYSQL_DB",
    "resume_analyzer"
)

app.config["MYSQL_CURSORCLASS"] = "DictCursor"

mysql = MySQL(app)


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template(
        "index.html",
        name=session.get("user_name")
    )


# =========================================================
# REGISTER PAGE
# =========================================================

@app.route("/register")
def register():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return render_template("register.html")


# =========================================================
# REGISTER USER
# =========================================================

@app.route("/register", methods=["POST"])
def register_user():

    name = request.form.get(
        "name",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    password = request.form.get(
        "password",
        ""
    )


    if not name or not email or not password:

        return render_template(
            "register.html",
            error="All fields are required."
        )


    if len(password) < 6:

        return render_template(
            "register.html",
            error="Password must contain at least 6 characters."
        )


    cursor = mysql.connection.cursor()


    cursor.execute(
        """
        SELECT id
        FROM users
        WHERE email = %s
        """,
        (email,)
    )


    existing_user = cursor.fetchone()


    if existing_user:

        cursor.close()

        return render_template(
            "register.html",
            error="Email already registered."
        )


    hashed_password = generate_password_hash(
        password
    )


    cursor.execute(
        """
        INSERT INTO users
        (
            name,
            email,
            password
        )
        VALUES
        (
            %s,
            %s,
            %s
        )
        """,
        (
            name,
            email,
            hashed_password
        )
    )


    mysql.connection.commit()

    cursor.close()


    return redirect(
        url_for("login")
    )


# =========================================================
# LOGIN PAGE
# =========================================================

@app.route("/login")
def login():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return render_template(
        "login.html"
    )


# =========================================================
# LOGIN USER
# =========================================================

@app.route("/login", methods=["POST"])
def login_user():

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    password = request.form.get(
        "password",
        ""
    )


    cursor = mysql.connection.cursor()


    cursor.execute(
        """
        SELECT
            id,
            name,
            email,
            password
        FROM users
        WHERE email = %s
        """,
        (email,)
    )


    user = cursor.fetchone()

    cursor.close()


    if user and check_password_hash(
        user["password"],
        password
    ):

        session["user_id"] = user["id"]

        session["user_name"] = user["name"]

        return redirect(
            url_for("dashboard")
        )


    return render_template(
        "login.html",
        error="Invalid email or password."
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    cursor = mysql.connection.cursor()


    cursor.execute(
        """
        SELECT
            id,
            resume_quality_score,
            match_score,
            match_level,
            matched_skills,
            missing_skills,
            recommended_roles,
            ai_recommendation,
            created_at
        FROM resume_results
        WHERE user_id = %s
        ORDER BY created_at DESC
        """,
        (
            session["user_id"],
        )
    )


    results = cursor.fetchall()

    cursor.close()


    return render_template(
        "dashboard.html",
        results=results,
        name=session.get("user_name")
    )


# =========================================================
# ANALYSIS DETAILS
# =========================================================

@app.route("/analysis/<int:analysis_id>")
def analysis_details(analysis_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    cursor = mysql.connection.cursor()


    cursor.execute(
        """
        SELECT
            id,
            resume_quality_score,
            match_score,
            match_level,
            matched_skills,
            missing_skills,
            recommended_roles,
            ai_recommendation,
            created_at
        FROM resume_results
        WHERE id = %s
        AND user_id = %s
        """,
        (
            analysis_id,
            session["user_id"]
        )
    )


    result = cursor.fetchone()

    cursor.close()


    if not result:

        return "Analysis not found.", 404


    # =====================================================
    # MATCHED SKILLS
    # =====================================================

    matched_skills = []

    if result["matched_skills"]:

        matched_skills = [
            skill.strip()
            for skill in result["matched_skills"].split(",")
            if skill.strip()
        ]


    # =====================================================
    # MISSING SKILLS
    # =====================================================

    missing_skills = []

    if result["missing_skills"]:

        missing_skills = [
            skill.strip()
            for skill in result["missing_skills"].split(",")
            if skill.strip()
        ]


    # =====================================================
    # RECOMMENDED ROLES
    # =====================================================

    recommended_roles = []

    if result["recommended_roles"]:

        role_items = result[
            "recommended_roles"
        ].split(",")


        for role_data in role_items:

            role_data = role_data.strip()


            if not role_data:
                continue


            if "(" in role_data and "%" in role_data:

                role_name = role_data.rsplit(
                    "(",
                    1
                )[0].strip()


                score_text = role_data.rsplit(
                    "(",
                    1
                )[1]


                score_text = score_text.replace(
                    "%)",
                    ""
                ).strip()


                try:

                    role_score = int(
                        score_text
                    )

                except ValueError:

                    role_score = 0


                recommended_roles.append(
                    {
                        "role": role_name,
                        "score": role_score
                    }
                )

            else:

                recommended_roles.append(
                    {
                        "role": role_data,
                        "score": 0
                    }
                )


    return render_template(
        "analysis_details.html",
        result=result,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        recommended_roles=recommended_roles
    )


# =========================================================
# JOB DESCRIPTION PAGE
# =========================================================

@app.route("/job")
def job():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    return render_template(
        "job.html"
    )


# =========================================================
# RESUME UPLOAD
# =========================================================

@app.route("/upload", methods=["POST"])
def upload_resume():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    file = request.files.get(
        "resume"
    )


    if not file or file.filename == "":

        return render_template(
            "index.html",
            name=session.get("user_name"),
            error="Please select a resume PDF."
        )


    if not file.filename.lower().endswith(".pdf"):

        return render_template(
            "index.html",
            name=session.get("user_name"),
            error="Only PDF files are supported."
        )


    try:

        file_data = file.read()

        pdf = fitz.open(
            stream=file_data,
            filetype="pdf"
        )

    except Exception:

        return render_template(
            "index.html",
            name=session.get("user_name"),
            error="Unable to read the PDF file."
        )


    # =====================================================
    # EXTRACT TEXT
    # =====================================================

    resume_text = ""


    for page in pdf:

        resume_text += page.get_text()


    pdf.close()


    if not resume_text.strip():

        return render_template(
            "index.html",
            name=session.get("user_name"),
            error="Could not extract text from this PDF."
        )


    # =====================================================
    # SKILL CATEGORIES
    # =====================================================

    skill_categories = {

        "Programming": [
            "Python",
            "Java",
            "C++",
            "JavaScript"
        ],

        "Web Development": [
            "HTML",
            "CSS",
            "JavaScript",
            "Flask",
            "Django",
            "REST API"
        ],

        "Database": [
            "SQL",
            "MySQL",
            "PostgreSQL",
            "MongoDB"
        ],

        "AI / Machine Learning": [
            "Machine Learning",
            "Deep Learning",
            "TensorFlow",
            "PyTorch",
            "Pandas",
            "NumPy"
        ],

        "Cloud": [
            "AWS",
            "Azure",
            "Google Cloud"
        ],

        "Tools": [
            "Git",
            "GitHub",
            "Docker"
        ],

        "Analytics": [
            "Power BI",
            "Tableau"
        ]
    }


    # =====================================================
    # DETECT RESUME SKILLS
    # =====================================================

    resume_lower = resume_text.lower()

    detected_categories = {}

    all_found_skills = []


    for category, skills in skill_categories.items():

        found = []


        for skill in skills:

            if skill.lower() in resume_lower:

                found.append(skill)


                if skill not in all_found_skills:

                    all_found_skills.append(
                        skill
                    )


        if found:

            detected_categories[
                category
            ] = found


    # =====================================================
    # RESUME QUALITY SCORE
    # =====================================================

    score = 0


    if len(all_found_skills) >= 8:

        score += 25

    elif len(all_found_skills) >= 5:

        score += 20

    elif len(all_found_skills) >= 3:

        score += 15

    elif len(all_found_skills) >= 1:

        score += 10


    if (
        "project" in resume_lower
        or "projects" in resume_lower
    ):

        score += 20


    if "education" in resume_lower:

        score += 15


    if (
        "experience" in resume_lower
        or "internship" in resume_lower
    ):

        score += 15


    if "@" in resume_text:

        score += 10


    if "github" in resume_lower:

        score += 5


    if "linkedin" in resume_lower:

        score += 5


    resume_quality_score = min(
        score,
        100
    )


    # =====================================================
    # RESUME LEVEL
    # =====================================================

    if resume_quality_score >= 80:

        resume_level = "Excellent Resume"

    elif resume_quality_score >= 60:

        resume_level = "Good Resume"

    elif resume_quality_score >= 40:

        resume_level = "Needs Improvement"

    else:

        resume_level = "Needs Major Improvement"


    # =====================================================
    # SAVE RESUME INFORMATION IN SESSION
    # =====================================================

    session["resume_skills"] = all_found_skills

    session["resume_categories"] = detected_categories

    session["resume_quality_score"] = resume_quality_score

    session["resume_level"] = resume_level


    return redirect(
        url_for("job")
    )


# =========================================================
# MATCH RESUME WITH JOB DESCRIPTION
# =========================================================

@app.route("/match", methods=["POST"])
def match_resume():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    job_description = request.form.get(
        "job_description",
        ""
    ).strip()


    if not job_description:

        return render_template(
            "job.html",
            error="Please enter the job description."
        )


    # =====================================================
    # GET RESUME INFORMATION
    # =====================================================

    resume_skills = session.get(
        "resume_skills",
        []
    )

    resume_categories = session.get(
        "resume_categories",
        {}
    )

    resume_quality_score = session.get(
        "resume_quality_score",
        0
    )

    resume_level = session.get(
        "resume_level",
        "Not Available"
    )


    # =====================================================
    # SUPPORTED SKILLS
    # =====================================================

    skills_list = [

        "Python",
        "Java",
        "C++",

        "SQL",
        "MySQL",
        "PostgreSQL",
        "MongoDB",

        "HTML",
        "CSS",
        "JavaScript",

        "Flask",
        "Django",
        "REST API",

        "Machine Learning",
        "Deep Learning",
        "TensorFlow",
        "PyTorch",

        "Pandas",
        "NumPy",

        "Git",
        "GitHub",
        "Docker",

        "Power BI",
        "Tableau",

        "AWS",
        "Azure",
        "Google Cloud"
    ]


    job_lower = job_description.lower()


    # =====================================================
    # FIND REQUIRED SKILLS
    # =====================================================

    required_skills = []


    for skill in skills_list:

        if skill.lower() in job_lower:

            required_skills.append(
                skill
            )


    # =====================================================
    # FIND MATCHED SKILLS
    # =====================================================

    resume_skills_lower = [
        skill.lower()
        for skill in resume_skills
    ]


    matched_skills = []


    for skill in required_skills:

        if skill.lower() in resume_skills_lower:

            matched_skills.append(
                skill
            )


    # =====================================================
    # FIND MISSING SKILLS
    # =====================================================

    missing_skills = []


    for skill in required_skills:

        if skill not in matched_skills:

            missing_skills.append(
                skill
            )


    # =====================================================
    # MATCH SCORE
    # =====================================================

    if required_skills:

        match_score = round(
            (
                len(matched_skills)
                /
                len(required_skills)
            ) * 100
        )

    else:

        match_score = 0


    # =====================================================
    # MATCH LEVEL
    # =====================================================

    if match_score >= 80:

        match_level = "Strong Match"

    elif match_score >= 60:

        match_level = "Good Match"

    elif match_score >= 40:

        match_level = "Moderate Match"

    else:

        match_level = "Low Match"


    # =====================================================
    # AI CAREER RECOMMENDATION
    # =====================================================

    if matched_skills:

        strengths = ", ".join(
            matched_skills
        )

    else:

        strengths = "your current technical skills"


    if missing_skills:

        missing = ", ".join(
            missing_skills
        )


        ai_recommendation = (

            f"Your resume shows good strength in "
            f"{strengths}. "

            f"For this job, the important skill gaps "
            f"are {missing}. "

            f"Focus on learning these skills through "
            f"practical projects and hands-on practice. "

            f"Add relevant projects, certifications, "
            f"and measurable achievements to your resume. "

            f"Your current job compatibility score is "
            f"{match_score}%. "

            f"Improving these areas can strengthen "
            f"your profile."

        )

    else:

        ai_recommendation = (

            f"Your resume matches all the detected "
            f"technical requirements for this job. "

            f"Your current compatibility score is "
            f"{match_score}%. "

            f"Continue strengthening your existing "
            f"skills through real-world projects, "
            f"internships, and practical experience."

        )


    # =====================================================
    # CAREER ROLES
    # =====================================================

    career_roles = {

        "Python Developer": [
            "Python",
            "Git",
            "GitHub"
        ],

        "Backend Developer": [
            "Python",
            "Flask",
            "Django",
            "SQL",
            "MySQL",
            "REST API"
        ],

        "Full Stack Developer": [
            "Python",
            "HTML",
            "CSS",
            "JavaScript",
            "Flask",
            "Django",
            "SQL"
        ],

        "Data Analyst": [
            "Python",
            "SQL",
            "Pandas",
            "NumPy",
            "Power BI",
            "Tableau"
        ],

        "Machine Learning Engineer": [
            "Python",
            "Machine Learning",
            "Pandas",
            "NumPy",
            "TensorFlow",
            "PyTorch"
        ],

        "Cloud Developer": [
            "Python",
            "AWS",
            "Azure",
            "Docker",
            "Git"
        ]
    }


    # =====================================================
    # CALCULATE CAREER ROLE SCORES
    # =====================================================

    role_scores = []


    for role, role_skills in career_roles.items():

        matched_count = 0


        for skill in role_skills:

            if skill.lower() in resume_skills_lower:

                matched_count += 1


        if role_skills:

            role_score = round(
                (
                    matched_count
                    /
                    len(role_skills)
                ) * 100
            )

        else:

            role_score = 0


        role_scores.append(
            {
                "role": role,
                "score": role_score
            }
        )


    role_scores.sort(
        key=lambda item: item["score"],
        reverse=True
    )


    recommended_roles = role_scores[:5]


    # =====================================================
    # CONVERT LISTS TO TEXT FOR MYSQL
    # =====================================================

    matched_text = ", ".join(
        matched_skills
    )


    missing_text = ", ".join(
        missing_skills
    )


    recommended_text = ", ".join(
        [
            f"{item['role']} ({item['score']}%)"
            for item in recommended_roles
        ]
    )


    # =====================================================
    # SAVE ANALYSIS TO MYSQL
    # =====================================================

    cursor = mysql.connection.cursor()


    cursor.execute(
        """
        INSERT INTO resume_results
        (
            user_id,
            resume_quality_score,
            match_score,
            match_level,
            matched_skills,
            missing_skills,
            recommended_roles,
            ai_recommendation
        )
        VALUES
        (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        """,
        (
            session["user_id"],
            resume_quality_score,
            match_score,
            match_level,
            matched_text,
            missing_text,
            recommended_text,
            ai_recommendation
        )
    )


    mysql.connection.commit()

    cursor.close()


    # =====================================================
    # RESULT PAGE
    # =====================================================

    return render_template(
        "result.html",
        match_score=match_score,
        match_level=match_level,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        ai_recommendation=ai_recommendation,
        resume_quality_score=resume_quality_score,
        resume_level=resume_level,
        resume_categories=resume_categories,
        recommended_roles=recommended_roles
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )