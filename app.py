import os
import uuid
from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for
from azure.storage.blob import BlobServiceClient
from azure.cognitiveservices.vision.customvision.prediction import CustomVisionPredictionClient
from msrest.authentication import ApiKeyCredentials
import pyodbc
import requests

from flask import session
import secrets  # Ajoutez cette ligne pour l'importation de secrets

# --- Génération de la clé secrète ---
secret_key = secrets.token_hex(24)  # Génère une clé secrète de 24 octets en hexadécimal
print(secret_key)  # Optionnel, pour afficher la clé générée dans la console

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = secret_key  # Attribuez la clé secrète à l'application Flask

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
                session['user_id'] = user[0]  # Stocker l'ID de l'utilisateur dans la session
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
    user_id = session.get('user_id')  # Récupérer l'ID de l'utilisateur connecté
    if not user_id:
        return redirect(url_for('login'))  # Si l'utilisateur n'est pas connecté, rediriger vers la connexion

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT Quizzes.Title, QuizResults.Score
            FROM QuizResults
            LEFT JOIN Quizzes ON QuizResults.QuizId = Quizzes.QuizId
            WHERE QuizResults.UserId = ?
        """, (user_id,))
        results = cursor.fetchall()
        cursor.close()

        # Si l'utilisateur n'a pas encore de résultats, afficher un score de 0
        if not results:
            total_score = 0
        else:
            # Calculer la moyenne des scores si nécessaire, sinon récupérer simplement le score
            total_score = round(sum(result[1] for result in results) / len(results) if results else 0)

        # Vérifier que les résultats sont bien récupérés
        print(f"Results retrieved: {results}")
        print(f"Total score calculated: {total_score}")

        return render_template('dashboard.html', results=results, total_score=total_score)
    else:
        return render_template('dashboard.html', error="Erreur de connexion à la base de données.")





def calculate_total_score(results):
    if not results:
        return 0  # Si aucun résultat n'est trouvé, le score est 0

    total_score = sum(result[1] for result in results)  # Additionner tous les scores
    return total_score / len(results)  # Retourner la moyenne





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




@app.route('/quiz/<string:quiz_id>', methods=['GET'])
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
    # Récupérer l'identifiant de l'utilisateur à partir de la session
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))  # Si l'utilisateur n'est pas connecté

    correct_answers = 0
    conn = get_db_connection()
    cursor = conn.cursor()

    # Récupérer les questions du quiz
    cursor.execute("SELECT * FROM QuizQuestions WHERE QuizId = ?", (quiz_id,))
    questions = cursor.fetchall()

    # Vérifier les réponses de l'utilisateur pour chaque question
    for question in questions:
        # Récupérer la réponse de l'utilisateur pour chaque question
        user_answer = request.form.get(f'question_{question.QuestionId}')
        
        # Vérification de la réponse, ignorer la casse et les espaces
        if user_answer and user_answer.strip().lower() == question.CorrectAnswer.strip().lower():
            correct_answers += 1

    total_questions = len(questions)
    score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0

    cursor.close()

    # Enregistrer les résultats dans la base de données si l'utilisateur est connecté
    if user_id:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO QuizResults (UserId, QuizId, CorrectAnswers, TotalQuestions, Score)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, quiz_id, correct_answers, total_questions, score))
        conn.commit()

    return redirect(url_for('results', quiz_id=quiz_id, score=score))






@app.route('/results/<int:quiz_id>/<int:score>', methods=['GET'])
def results(quiz_id, score):
    # Connexion à la base de données pour récupérer les détails du quiz
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Quizzes WHERE QuizId = ?", (quiz_id,))
        quiz = cursor.fetchone()  # Récupère les informations du quiz
        cursor.close()
        
        # Rendu de la page des résultats avec le score
        return render_template('results.html', quiz=quiz, score=score)
    else:
        return render_template('results.html', error="Erreur de connexion à la base de données.")






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
            # Insérer l'utilisateur dans la table Users
            cursor.execute("""
                INSERT INTO Users (UserName, Email, PasswordHash, PredictedGender)
                VALUES (?, ?, ?, ?)
            """, (username, email, password, predicted_gender))
            conn.commit()  # Sauvegarder l'utilisateur
            
            # Récupérer l'ID de l'utilisateur nouvellement ajouté
            cursor.execute("SELECT UserId FROM Users WHERE UserName = ?", (username,))
            user_id = cursor.fetchone()[0]

            # Ajouter une entrée dans la table QuizResults avec un score initial de 0
            cursor.execute("""
                INSERT INTO QuizResults (UserId, QuizId, CorrectAnswers, TotalQuestions, Score)
                VALUES (?, NULL, 0, 0, 0)
            """, (user_id,))
            conn.commit()
            print(f"User {username} registered successfully with initial score set to 0.")
        except Exception as e:
            print(f"Error while saving user: {e}")
        finally:
            cursor.close()
            conn.close()
    else:
        print("Failed to save user due to database connection error.")



if __name__ == '__main__':
    app.run(debug=True)
