# Convertiseur_Tel_En_Cam

<img width="1248" height="832" alt="OIG1" src="https://github.com/user-attachments/assets/fe4f42a4-fd8a-4276-9ce9-058785659b5e" />


**Convertissez votre téléphone en caméra de surveillance et visualisez le flux en direct sur votre PC, dans le même réseau local.**

[![Python](https://img.shields.io/badge/python-3.9+-green.svg)](https://www.python.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.8+-red.svg)](https://opencv.org/)

---

## 🚀 Fonctionnalités

- **Flux vidéo en direct** depuis une IP Webcam installée sur votre téléphone.
- **Interface graphique moderne** aux couleurs vert/rouge (Tkinter).
- **Détection de mouvement** en temps réel avec seuils configurables.
- **Enregistrement automatique** des événements de mouvement.
- **Snapshots manuels et automatiques**.
- **Alertes** sonores, webhook et Telegram.
- **Dashboard web** intégré accessible depuis un navigateur.
- **Base de données SQLite** pour l'historique des événements.
- **Export CSV** des événements.
- **Scanner réseau** pour trouver rapidement l'IP du téléphone.
- **Vision nocturne**, flip, rotation et overlay horodaté.
- **Reconnexion automatique** en cas de perte de flux.
- **Nettoyage automatique** des anciennes vidéos et images.

---

## 📋 Prérequis

- Un téléphone Android/iOS avec une application IP Webcam (ex: **IP Webcam** sur Android).
- Un PC sous Windows, macOS ou Linux.
- Python **3.9 ou supérieur**.
- Le téléphone et le PC doivent être connectés au **même réseau Wi-Fi**.

---

## ⚙️ Installation

1. **Cloner ou télécharger** ce projet.

2. **Créer un environnement virtuel** (recommandé) :

   ```bash
   python -m venv venv
   ```

3. **Activer l'environnement** :

   - Windows :
     ```bash
     venv\Scripts\activate
     ```
   - Linux/macOS :
     ```bash
     source venv/bin/activate
     ```

4. **Installer les dépendances** :

   ```bash
   pip install -r requirements.txt
   ```

---

## 📱 Configuration du téléphone

1. Installez **IP Webcam** (ou une application équivalente) sur votre téléphone.
2. Lancez l'application et démarrez le serveur.
3. Notez l'**adresse IP** et le **port** affichés (ex: `192.168.1.50:8080`).
4. Assurez-vous que le téléphone reste allumé et ne se met pas en veille.

---

## ▶️ Lancement

```bash
python convertiseur_tel_en_cam.py
```

Une fenêtre s'ouvre. Saisissez l'IP et le port du téléphone, puis cliquez sur **Connexion**.

---

## 🌐 Dashboard web

Une fois connecté, ouvrez un navigateur sur votre PC (ou un autre appareil du réseau) :

```
http://<IP_DE_VOTRE_PC>:8090/
```

Par exemple :

```
http://192.168.1.10:8090/
```

---

## 📁 Structure des dossiers

```
.
├── convertiseur_tel_en_cam.py   # Application principale
├── requirements.txt             # Dépendances Python
├── README.md                    # Documentation
├── config.json                  # Configuration sauvegardée
├── surveillance.db              # Base de données des événements
├── recordings/                  # Vidéos enregistrées
├── snapshots/                   # Captures d'écran
├── exports/                     # Fichiers CSV exportés
├── logs/                        # Journaux
└── data/                        # Données de l'application
```

---

## 🛠️ Dépannage

| Problème | Solution |
|----------|----------|
| `Connexion impossible` | Vérifiez que le téléphone et le PC sont sur le même Wi-Fi. |
| `Aucune image` | Vérifiez l'IP, le port et le chemin du flux (`/video` par défaut). |
| `La fenêtre est lente` | Réduisez la résolution ou les FPS dans les options. |
| `Erreur cv2` | Réinstallez OpenCV : `pip install --upgrade opencv-python` |
| `Alertes Telegram non reçues` | Vérifiez le token et le chat_id. |

---

## 📝 Licence

Ce projet est sous licence **MIT**.

Auteur : **HACKERS_TCHAD**

---

## 💡 Conseils

- Placez le téléphone dans un endroit stable avec une bonne vue.
- Utilisez un support pour éviter les mouvements parasites.
- Activez la charge du téléphone pour une surveillance prolongée.
- Sécurisez votre réseau Wi-Fi pour éviter l'accès non autorisé.
