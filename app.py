import os
import uuid
from flask import Flask, request, jsonify

from azure.storage.blob import BlobServiceClient
from azure.cognitiveservices.vision.customvision.prediction import CustomVisionPredictionClient
from msrest.authentication import ApiKeyCredentials
from azure.cognitiveservices.vision.customvision.prediction.models import ImagePrediction

import pyodbc

app = Flask(__name__)


# Configuration pour Azure Blob Storage
blob_connection_string = os.getenv("AZURE_BLOB_CONNECTION_STRING")
blob_service_client = BlobServiceClient.from_connection_string(blob_connection_string)
container_name = "bloblinguistique"

# Configuration pour Azure Custom Vision
prediction_key = os.getenv("CUSTOM_VISION_PREDICTION_KEY")
endpoint = "https://customvisionprojetlinguistique.cognitiveservices.azure.com/"
project_id = "55ea68cc-53af-4710-9664-e208dd4384e9"
publish_iteration_name = "publish_iteration_name"

# Configuration pour Azure SQL Database
sql_server = "appli-linguistique-sql.database.windows.net"
database = "appliLinguistiqueDB"
username = "sqladmin"
password = os.getenv("SQL_PASSWORD")
driver = "{ODBC Driver 17 for SQL Server}"

# Connexion à la base de données
def get_db_connection():
    conn = pyodbc.connect(f'DRIVER={driver};SERVER={sql_server};PORT=1433;DATABASE={database};UID={username};PWD={password}')
    return conn

# Route pour télécharger l'image et prédire le genre
@app.route('/upload-image', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Générez un nom unique pour le fichier
    file_name = str(uuid.uuid4()) + os.path.splitext(file.filename)[1]

    # Téléchargez l'image dans Azure Blob Storage
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=file_name)
    blob_client.upload_blob(file)
    
    # Obtenez l'URL du fichier téléchargé
    image_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{file_name}"

    # Prédire le genre via Custom Vision
    predicted_gender = predict_gender(image_url)

    # Sauvegarder l'utilisateur dans la base de données (nom, email, mot de passe, genre prédit)
    save_user_to_db(request.form['username'], request.form['email'], request.form['password'], predicted_gender)

    return jsonify({"predictedGender": predicted_gender})

# Fonction pour prédire le genre avec Azure Custom Vision
def predict_gender(image_url):
    # Créez le client Custom Vision
    credentials = ApiKeyCredentials(in_headers={"Prediction-Key": prediction_key})
    predictor = CustomVisionPredictionClient(endpoint, credentials)

    # Appel à l'API de prédiction
    image_data = open(image_url, "rb")
    prediction = predictor.classify_image_url(project_id, publish_iteration_name, image_url)
    
    # Retourne la première prédiction (homme ou femme)
    return prediction.predictions[0].tag_name

# Fonction pour enregistrer l'utilisateur dans la base de données
def save_user_to_db(username, email, password, predicted_gender):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Insérer l'utilisateur dans la base de données
    cursor.execute("""
    INSERT INTO Users (UserName, Email, PasswordHash, PredictedGender)
    VALUES (?, ?, ?, ?)
    """, (username, email, password, predicted_gender))

    conn.commit()
    cursor.close()
    conn.close()

if __name__ == '_main_':
    app.run(debug=True)