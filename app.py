import os
import uuid
from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for
from azure.storage.blob import BlobServiceClient
from azure.cognitiveservices.vision.customvision.prediction import CustomVisionPredictionClient
from msrest.authentication import ApiKeyCredentials
import pyodbc
import requests
from flask import session
app = Flask(__name__, static_folder='static', template_folder='templates')

# --- Clés et configurations ---
# Configuration pour Azure Blob Storage
blob_connection_string = "DefaultEndpointsProtocol=https;AccountName=bloblinguistique;AccountKey=COAUxu7GXT7e4y7bLIBHxuPM5QzN5nZSuK/FVVUAFPcwcR53il7te3YeFTX96iimhpWLDH7FYoRw+AStUJUuOA==;EndpointSuffix=core.windows.net"
blob_service_client = BlobServiceClient.from_connection_string(blob_connection_string)
container_name = "photousers"

# Configuration pour Azure Custom Vision
prediction_key = "FMFcDDm7wdaZcZkDArKt72IW2541AAy74SVGGnuvMoaTgmUxENceJQQJ99ALAC5RqLJXJ3w3AAAIACOGqZAu"
endpoint = "https://customvisionprojetlinguistique-prediction.cognitiveservices.azure.com/"
project_id = "55ea68cc-53af-4710-9664-e208dd4384e9"
publish_iteration_name = "publish_iteration_name"

# Configuration pour Azure SQL Database
sql_server = "appli-linguistique-sql.database.windows.net"
database = "appliLinguistiqueDB"
username = "sqladmin"
password = "Meryemsarahoussam1234"
driver = "{ODBC Driver 17 for SQL Server}"

# Connexion à la base de données
def get_db_connection():
    try:
        conn = pyodbc.connect(f'DRIVER={driver};SERVER={sql_server};PORT=1433;DATABASE={database};UID={username};PWD={password}')
        print("Database connection successful.")
        return conn
    except pyodbc.Error as e:
        print(f"Database connection failed: {e}")
        return None


# --- Routes pour les pages HTML ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Récupérer les informations du formulaire
        username = request.form['username']
        password = request.form['password']

        # Connexion à la base de données et vérification des informations
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Users WHERE UserName = ?", (username,))
            user = cursor.fetchone()
            cursor.close()

            # Vérification si l'utilisateur existe et si le mot de passe correspond
            if user and user[3] == password:  # 3 correspond à l'indice de 'PasswordHash'
                print(f"User {username} logged in successfully")
                return redirect(url_for('dashboard'))  # Rediriger vers le tableau de bord si les informations sont correctes
            else:
                return render_template('login.html', error="Nom d'utilisateur ou mot de passe incorrect.")
        else:
            return render_template('login.html', error="Erreur de connexion à la base de données.")
    
    return render_template('login.html')  # Afficher le formulaire de connexion

@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    user_id = 1  # Remplacez cela par l'ID réel de l'utilisateur

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        # Récupérer les résultats de tous les quiz de l'utilisateur
        cursor.execute("""
            SELECT Quizzes.Title, QuizResults.Score
            FROM QuizResults
            JOIN Quizzes ON QuizResults.QuizId = Quizzes.QuizId
            WHERE QuizResults.UserId = ?
        """, (user_id,))
        results = cursor.fetchall()  # Récupérer les résultats sous forme de tuple
        cursor.close()

        # Calculer le score total de l'utilisateur
        total_score = calculate_total_score(results)

        return render_template('dashboard.html', results=results, total_score=total_score)
    else:
        return render_template('dashboard.html', error="Erreur de connexion à la base de données.")


def calculate_total_score(results):
    total_score = 0
    total_quizzes = len(results)

    if total_quizzes > 0:
        for result in results:
            total_score += result[1]  # L'indice 1 correspond à "Score"
        
        # Arrondir à 2 décimales
        return round(total_score / total_quizzes, 2)
    else:
        return 0




@app.route('/quiz-list')
def quiz_list():
    # Connexion à la base de données et récupération des quizs
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Quizzes")  # Récupère tous les quizs
        quizzes = cursor.fetchall()  # Récupère toutes les lignes de résultats
        cursor.close()
        return render_template('quiz_list.html', quizzes=quizzes)  # Passer les quizs à la template
    else:
        return render_template('quiz_list.html', error="Erreur de connexion à la base de données.")




@app.route('/quiz/<int:quiz_id>', methods=['GET'])
def quiz(quiz_id):
    # Connexion à la base de données et récupération des questions pour le quiz spécifique
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM QuizQuestions WHERE QuizId = ?", (quiz_id,))
        questions = cursor.fetchall()
        cursor.execute("SELECT * FROM Quizzes WHERE QuizId = ?", (quiz_id,))
        quiz = cursor.fetchone()  # Récupère les informations du quiz
        cursor.close()
        return render_template('quiz.html', questions=questions, quiz=quiz)  # Passer les questions et le quiz à la template
    else:
        return render_template('quiz.html', error="Erreur de connexion à la base de données.")
@app.route('/submit-quiz/<int:quiz_id>', methods=['POST'])
def submit_quiz(quiz_id):
    # Récupérer les réponses de l'utilisateur
    user_id = 1  # Remplacer par l'ID réel de l'utilisateur
    correct_answers = 0

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        # Récupérer les bonnes réponses pour les questions du quiz
        cursor.execute("SELECT * FROM QuizQuestions WHERE QuizId = ?", (quiz_id,))
        questions = cursor.fetchall()

        # Vérifier les réponses de l'utilisateur
        for question in questions:
            user_answer = request.form.get(f'question_{question.QuestionId}')
            if user_answer == question.CorrectAnswer:
                correct_answers += 1

        total_questions = len(questions)
        score = (correct_answers / total_questions) * 100

        # Enregistrer les résultats dans la table QuizResults
        cursor.execute("""
            INSERT INTO QuizResults (UserId, QuizId, CorrectAnswers, TotalQuestions, Score)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, quiz_id, correct_answers, total_questions, score))

        conn.commit()
        cursor.close()

        return redirect(url_for('results', quiz_id=quiz_id, score=score))

    else:
        return render_template('quiz.html', error="Erreur de connexion à la base de données.")


@app.route('/results', methods=['GET'])
def results():
    score = request.args.get('score')
    return render_template('results.html', score=score)


@app.route('/logout')
def logout():
    # Simplement rediriger vers la page de connexion sans utiliser de sessions
    return redirect(url_for('login'))  # Redirige vers la page de connexion

# Route pour la page d'inscription
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Récupérer les données du formulaire
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        profile_picture = request.files['profile_picture']

        # Générez un nom unique pour le fichier
        file_name = str(uuid.uuid4()) + os.path.splitext(profile_picture.filename)[1]

        try:
            # Téléchargez l'image dans Azure Blob Storage avec overwrite=True pour éviter l'erreur de conflit
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=file_name)
            blob_client.upload_blob(profile_picture, overwrite=True)  # Forcer l'écrasement si le fichier existe

            # Obtenez l'URL de l'image téléchargée
            image_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{file_name}"

            # Vérifiez si l'URL de l'image est accessible
            if not is_image_accessible(image_url):
                return render_template('register.html', error="L'image n'est pas accessible. Veuillez réessayer.")

            # Prédire le genre via Custom Vision
            predicted_gender = predict_gender(image_url)

            # Sauvegarder l'utilisateur dans la base de données
            save_user_to_db(username, email, password, predicted_gender)

            # Rediriger vers la page de connexion après l'enregistrement
            return redirect(url_for('login'))
        
        except Exception as e:
            return render_template('register.html', error=f"Erreur lors du téléchargement de l'image: {e}")

    return render_template('register.html')  # Afficher le formulaire d'inscription

# Fonction pour prédire le genre avec Azure Custom Vision
def predict_gender(image_url):
    try:
        # Créez le client Custom Vision avec vos clés d'API
        credentials = ApiKeyCredentials(in_headers={"Prediction-Key": prediction_key})
        predictor = CustomVisionPredictionClient(endpoint, credentials)

        # Effectuer la prédiction via l'API
        prediction = predictor.classify_image_url(project_id, publish_iteration_name, image_url)

        # Vérifier si la prédiction a renvoyé des résultats
        if prediction.predictions:
            predicted_tag = prediction.predictions[0].tag_name
            print(f"Predicted gender: {predicted_tag}")
            return predicted_tag
        else:
            print("No predictions found.")
            return "unknown"

    except Exception as e:
        print(f"Prediction failed: {e}")
        return "unknown"
    # Fonction pour vérifier si l'URL de l'image est accessible
def is_image_accessible(image_url):
    try:
        # Effectuer une requête HEAD pour vérifier l'accessibilité de l'image
        response = requests.head(image_url, timeout=5)
        if response.status_code == 200:
            print(f"L'image est accessible à l'URL: {image_url}")
            return True
        else:
            print(f"Erreur d'accès à l'image. Code d'état: {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"Erreur d'accès à l'image: {e}")
        return False

# Fonction pour enregistrer l'utilisateur dans la base de données
def save_user_to_db(username, email, password, predicted_gender):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO Users (UserName, Email, PasswordHash, PredictedGender)
                VALUES (?, ?, ?, ?)
            """, (username, email, password, predicted_gender))
            conn.commit()  # Sauvegarder les modifications
            print(f"User {username} registered successfully with gender {predicted_gender}")
        except Exception as e:
            print(f"Error while saving user: {e}")
        finally:
            cursor.close()
            conn.close()
    else:
        print("Failed to save user due to database connection error.")


if __name__ == '__main__':
    app.run(debug=True)
