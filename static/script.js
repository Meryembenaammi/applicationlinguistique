document.getElementById("signup-form").addEventListener("submit", function (event) {
    event.preventDefault();

    const username = document.getElementById("username").value;
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;
    const profilePicture = document.getElementById("profilePicture").files[0]; // Récupère l'image téléchargée

    // Envoyer l'image vers Azure Blob Storage
    const formData = new FormData();
    formData.append("image", profilePicture);

    fetch("https://<your-azure-storage-endpoint>/upload-image", {  // Remplacez par l'URL de votre API backend
        method: "POST",
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        const imageUrl = data.imageUrl;  // L'URL de l'image téléchargée dans Blob Storage
        // Appeler l'API Custom Vision pour prédire le genre
        predictGender(imageUrl);
    })
    .catch(error => {
        console.error("Erreur lors de l'upload de l'image :", error);
    });
});

// Fonction pour prédire le genre avec Custom Vision
function predictGender(imageUrl) {
    fetch("https://<your-web-app-url>/api/predict-gender", {  // Remplacez par votre API backend
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ imageUrl: imageUrl })
    })
    .then(response => response.json())
    .then(data => {
        const predictedGender = data.predictedGender;
        document.getElementById("predicted-gender").value = predictedGender;  // Afficher le genre prédit
        document.getElementById("message").innerText = "Inscription réussie!";
    })
    .catch(error => {
        console.error("Erreur lors de la prédiction du genre :", error);
        document.getElementById("message").innerText = "Erreur lors de l'inscription.";
    });
}