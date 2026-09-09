#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convertiseur_Tel_En_Cam — Convertir votre téléphone en caméra de surveillance.
Auteur   : CodePal
Version  : 4.0.0
Licence  : MIT

Cette application lance un serveur vidéo local. Sur votre téléphone, utilisez
une application d'IP Webcam (par ex. "IP Webcam" sur Android) ou la page web
fournie pour diffuser le flux vidéo. Ce PC affiche le flux, détecte les
mouvements, enregistre les événements, envoie des alertes et fournit une GUI.

Usage : python convertiseur_tel_en_cam.py

Recommandation : démarrez le serveur sur le téléphone AVANT de lancer ce script.
"""

import sys
import os
import time
import json
import base64
import hashlib
import hmac
import threading
import queue
import datetime
import logging
import logging.handlers
import re
import csv
import sqlite3
import socket
import urllib.request
import urllib.error
import urllib.parse
import subprocess
import platform
import textwrap
import random
import string
import math
import statistics
import itertools
import collections
import typing
import uuid
import warnings
import email.utils
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum, auto
from functools import lru_cache, wraps

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext

import cv2
import numpy as np
import imutils

# =============================================================================
# PARAMÈTRES & CONSTANTES
# =============================================================================

APP_NAME = "Convertiseur_Tel_En_Cam"
APP_VERSION = "4.0.0"
APP_AUTHOR = "CodePal"
APP_LICENSE = "MIT"

DEFAULT_HOST = "0.0.0.0"
DEFAULT_STREAM_PORT = 8080
DEFAULT_WEB_PORT = 8090
DEFAULT_PHONE_IP = "192.168.1.50"
DEFAULT_PHONE_PORT = 8080
DEFAULT_STREAM_PATH = "/video"
DEFAULT_USERNAME = ""
DEFAULT_PASSWORD = ""

DEFAULT_FPS = 30
DEFAULT_RESOLUTION_WIDTH = 1280
DEFAULT_RESOLUTION_HEIGHT = 720

MOTION_THRESHOLD_DEFAULT = 25
MOTION_CONTOUR_AREA_DEFAULT = 500
MOTION_BLUR_SIZE = 21
MOTION_HISTORY_SECONDS = 1.5
MOTION_COOLDOWN_SECONDS = 2.0

RECORDING_MAX_FILES = 100
RECORDING_MAX_AGE_DAYS = 7
SNAPSHOT_MAX_FILES = 200

LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3

DB_NAME = "surveillance.db"
CONFIG_NAME = "config.json"

COLORS = {
    "green_light": "#90EE90",
    "green_medium": "#32CD32",
    "green_dark": "#006400",
    "red_light": "#FF6B6B",
    "red_medium": "#DC143C",
    "red_dark": "#8B0000",
    "orange": "#FFA500",
    "yellow": "#FFD700",
    "white": "#FFFFFF",
    "black": "#000000",
    "gray_light": "#F0F0F0",
    "gray_medium": "#808080",
    "gray_dark": "#333333",
    "bg_dark": "#1E1E1E",
}

APP_TITLE = f"{APP_NAME} v{APP_VERSION} — Surveillance Téléphone → PC"

# =============================================================================
# JOURNALISATION
# =============================================================================

logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
file_handler = logging.handlers.RotatingFileHandler(
    f"{APP_NAME.lower()}.log", maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT
)
file_handler.setLevel(logging.DEBUG)

fmt = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(threadName)-12s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
console_handler.setFormatter(fmt)
file_handler.setFormatter(fmt)

if not logger.handlers:
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)


# =============================================================================
# ENUMS & DATACLASSES
# =============================================================================

class ConnectionState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()
    RECONNECTING = auto()


class RecordingState(Enum):
    STOPPED = auto()
    STARTING = auto()
    RECORDING = auto()
    STOPPING = auto()


class AlertLevel(Enum):
    INFO = auto()
    WARNING = auto()
    CRITICAL = auto()


@dataclass
class AppConfig:
    """Configuration persistante de l'application."""

    phone_ip: str = DEFAULT_PHONE_IP
    phone_port: int = DEFAULT_PHONE_PORT
    stream_path: str = DEFAULT_STREAM_PATH
    username: str = DEFAULT_USERNAME
    password: str = DEFAULT_PASSWORD
    host: str = DEFAULT_HOST
    stream_port: int = DEFAULT_STREAM_PORT
    web_port: int = DEFAULT_WEB_PORT
    fps: int = DEFAULT_FPS
    width: int = DEFAULT_RESOLUTION_WIDTH
    height: int = DEFAULT_RESOLUTION_HEIGHT
    motion_threshold: int = MOTION_THRESHOLD_DEFAULT
    motion_contour_area: int = MOTION_CONTOUR_AREA_DEFAULT
    enable_motion: bool = True
    enable_recording: bool = True
    enable_alerts: bool = True
    enable_audio: bool = False
    flip_horizontal: bool = False
    flip_vertical: bool = False
    rotate_90: bool = False
    rotate_180: bool = False
    rotate_270: bool = False
    detection_zones: list = None
    excluded_zones: list = None
    alert_sound: bool = True
    alert_email: str = ""
    alert_smtp_server: str = ""
    alert_smtp_port: int = 587
    alert_smtp_user: str = ""
    alert_smtp_password: str = ""
    alert_telegram_token: str = ""
    alert_telegram_chat_id: str = ""
    alert_webhook_url: str = ""
    language: str = "fr"
    theme: str = "dark_green_red"
    password_hash: str = ""
    password_salt: str = ""
    max_log_lines: int = 500
    auto_reconnect: bool = True
    reconnect_delay_seconds: int = 5
    use_hardware_accel: bool = False
    night_vision: bool = False
    timestamp_overlay: bool = True
    watermark_text: str = APP_NAME

    def __post_init__(self):
        if self.detection_zones is None:
            self.detection_zones = []
        if self.excluded_zones is None:
            self.excluded_zones = []

    def to_dict(self) -> dict:
        data = asdict(self)
        data["detection_zones"] = list(data.get("detection_zones", []))
        data["excluded_zones"] = list(data.get("excluded_zones", []))
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        kwargs = {}
        for key, default in cls.__dataclass_fields__.items():
            kwargs[key] = data.get(key, default.default)
        return cls(**kwargs)


@dataclass
class MotionEvent:
    """Un événement de mouvement détecté."""

    timestamp: float
    level: AlertLevel
    contour_area: float
    centroid: tuple
    frame_number: int
    image_path: str = ""
    video_clip_path: str = ""


# =============================================================================
# UTILITAIRES
# =============================================================================

def ensure_directories():
    """Crée les dossiers nécessaires à l'application."""
    dirs = ["recordings", "snapshots", "exports", "logs", "data"]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)


def get_local_ip() -> str:
    """Tente de déterminer l'adresse IP locale principale."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as exc:
        logger.warning("Impossible de déterminer l'IP locale : %s", exc)
        return "127.0.0.1"


def generate_nonce(length: int = 16) -> str:
    """Génère une chaîne aléatoire."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def hash_password(password: str, salt: str = None) -> tuple:
    """Hache un mot de passe avec PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = os.urandom(16).hex()
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
    return hashed, salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    """Vérifie un mot de passe."""
    computed, _ = hash_password(password, salt)
    return hmac.compare_digest(computed, hashed)


def sanitize_filename(name: str) -> str:
    """Nettoie une chaîne pour l'utiliser comme nom de fichier."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name)[:64]


def format_duration(seconds: float) -> str:
    """Formate une durée en HH:MM:SS."""
    return str(datetime.timedelta(seconds=int(seconds)))


def resize_keep_aspect(frame: np.ndarray, width: int, height: int) -> np.ndarray:
    """Redimensionne une image en conservant le ratio."""
    h, w = frame.shape[:2]
    scale = min(width / w, height / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    y_off = (height - new_h) // 2
    x_off = (width - new_w) // 2
    canvas[y_off : y_off + new_h, x_off : x_off + new_w] = resized
    return canvas


def draw_rounded_rectangle(
    img: np.ndarray,
    pt1: tuple,
    pt2: tuple,
    color: tuple,
    thickness: int = 1,
    radius: int = 10,
    line_type: int = cv2.LINE_AA,
) -> None:
    """Dessine un rectangle aux coins arrondis."""
    x1, y1 = pt1
    x2, y2 = pt2
    r = radius
    cv2.line(img, (x1 + r, y1), (x2 - r, y1), color, thickness, line_type)
    cv2.line(img, (x1 + r, y2), (x2 - r, y2), color, thickness, line_type)
    cv2.line(img, (x1, y1 + r), (x1, y2 - r), color, thickness, line_type)
    cv2.line(img, (x2, y1 + r), (x2, y2 - r), color, thickness, line_type)
    cv2.ellipse(img, (x1 + r, y1 + r), (r, r), 180, 0, 90, color, thickness, line_type)
    cv2.ellipse(img, (x2 - r, y1 + r), (r, r), 270, 0, 90, color, thickness, line_type)
    cv2.ellipse(img, (x1 + r, y2 - r), (r, r), 90, 0, 90, color, thickness, line_type)
    cv2.ellipse(img, (x2 - r, y2 - r), (r, r), 0, 0, 90, color, thickness, line_type)


# =============================================================================
# PERSISTANCE
# =============================================================================

class ConfigManager:
    """Gère le chargement et la sauvegarde de la configuration JSON."""

    def __init__(self, path: str = CONFIG_NAME):
        self.path = path

    def load(self) -> AppConfig:
        if not os.path.exists(self.path):
            logger.info("Aucune configuration trouvée, création des valeurs par défaut.")
            return AppConfig()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AppConfig.from_dict(data)
        except Exception as exc:
            logger.error("Erreur chargement config : %s", exc)
            return AppConfig()

    def save(self, config: AppConfig) -> bool:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception as exc:
            logger.error("Erreur sauvegarde config : %s", exc)
            return False


class DatabaseManager:
    """Gère la base de données SQLite des événements."""

    def __init__(self, path: str = None):
        if path is None:
            path = os.path.join("data", DB_NAME)
        self.path = path
        self.lock = threading.RLock()
        self._init_db()

    def _init_db(self):
        with self.lock, sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    datetime TEXT NOT NULL,
                    level TEXT NOT NULL,
                    area REAL,
                    centroid_x REAL,
                    centroid_y REAL,
                    frame_number INTEGER,
                    image_path TEXT,
                    video_clip_path TEXT,
                    notes TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start REAL NOT NULL,
                    end REAL,
                    duration_seconds REAL,
                    frames_received INTEGER DEFAULT 0,
                    motion_events INTEGER DEFAULT 0,
                    recordings_count INTEGER DEFAULT 0
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)"
            )
            conn.commit()

    def insert_event(self, event: MotionEvent, notes: str = "") -> int:
        with self.lock, sqlite3.connect(self.path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO events
                (timestamp, datetime, level, area, centroid_x, centroid_y,
                 frame_number, image_path, video_clip_path, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.timestamp,
                    datetime.datetime.fromtimestamp(event.timestamp).isoformat(),
                    event.level.name,
                    event.contour_area,
                    event.centroid[0] if event.centroid else None,
                    event.centroid[1] if event.centroid else None,
                    event.frame_number,
                    event.image_path,
                    event.video_clip_path,
                    notes,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def start_session(self) -> int:
        with self.lock, sqlite3.connect(self.path) as conn:
            cursor = conn.execute(
                "INSERT INTO sessions (start) VALUES (?)", (time.time(),)
            )
            conn.commit()
            return cursor.lastrowid

    def end_session(self, session_id: int, frames: int, motions: int, recordings: int):
        with self.lock, sqlite3.connect(self.path) as conn:
            start_row = conn.execute(
                "SELECT start FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            start = start_row[0] if start_row else time.time()
            end = time.time()
            conn.execute(
                """
                UPDATE sessions
                SET end = ?, duration_seconds = ?, frames_received = ?,
                    motion_events = ?, recordings_count = ?
                WHERE id = ?
                """,
                (end, end - start, frames, motions, recordings, session_id),
            )
            conn.commit()

    def get_events(
        self,
        start: float = None,
        end: float = None,
        level: AlertLevel = None,
        limit: int = 100,
    ) -> list:
        with self.lock, sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM events WHERE 1=1"
            params = []
            if start is not None:
                query += " AND timestamp >= ?"
                params.append(start)
            if end is not None:
                query += " AND timestamp <= ?"
                params.append(end)
            if level is not None:
                query += " AND level = ?"
                params.append(level.name)
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def export_csv(self, filepath: str, start: float = None, end: float = None) -> bool:
        events = self.get_events(start, end, limit=100000)
        if not events:
            return False
        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=events[0].keys())
                writer.writeheader()
                writer.writerows(events)
            return True
        except Exception as exc:
            logger.error("Erreur export CSV : %s", exc)
            return False


# =============================================================================
# GESTION DU FLUX VIDÉO
# =============================================================================

class VideoStreamSource:
    """Gère la connexion à un flux vidéo (IP webcam, fichier local, webcam PC)."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.capture = None
        self.state = ConnectionState.DISCONNECTED
        self.last_error = ""
        self.frames_received = 0
        self.frames_dropped = 0
        self.start_time = 0.0
        self.lock = threading.RLock()
        self._stop_event = threading.Event()

    @property
    def url(self) -> str:
        if self.config.username and self.config.password:
            creds = f"{urllib.parse.quote(self.config.username)}:{urllib.parse.quote(self.config.password)}@"
        else:
            creds = ""
        return f"http://{creds}{self.config.phone_ip}:{self.config.phone_port}{self.config.stream_path}"

    def build_capture(self) -> cv2.VideoCapture:
        """Construit un objet VideoCapture en fonction de la source."""
        source_str = self.url
        logger.info("Tentative de connexion à : %s", source_str)
        cap = cv2.VideoCapture(source_str)
        if not cap.isOpened():
            raise RuntimeError(f"Impossible d'ouvrir le flux : {source_str}")
        return cap

    def open(self) -> bool:
        with self.lock:
            self.state = ConnectionState.CONNECTING
            try:
                self.capture = self.build_capture()
                if self.config.width and self.config.height:
                    self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
                    self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
                if self.config.fps:
                    self.capture.set(cv2.CAP_PROP_FPS, self.config.fps)
                self.state = ConnectionState.CONNECTED
                self.start_time = time.time()
                self.frames_received = 0
                self.frames_dropped = 0
                self.last_error = ""
                logger.info("Flux vidéo connecté avec succès.")
                return True
            except Exception as exc:
                self.state = ConnectionState.ERROR
                self.last_error = str(exc)
                logger.error("Erreur connexion flux : %s", exc)
                return False

    def read(self) -> tuple:
        with self.lock:
            if self.capture is None or not self.capture.isOpened():
                self.state = ConnectionState.DISCONNECTED
                return False, None
            ok, frame = self.capture.read()
            if ok and frame is not None and frame.size > 0:
                self.frames_received += 1
                self.state = ConnectionState.CONNECTED
                return True, frame
            else:
                self.frames_dropped += 1
                return False, None

    def release(self):
        with self.lock:
            self.state = ConnectionState.DISCONNECTED
            if self.capture:
                try:
                    self.capture.release()
                except Exception as exc:
                    logger.warning("Erreur libération capture : %s", exc)
                self.capture = None
            self._stop_event.set()

    def is_open(self) -> bool:
        with self.lock:
            return self.capture is not None and self.capture.isOpened()

    def get_fps(self) -> float:
        with self.lock:
            if self.capture:
                return self.capture.get(cv2.CAP_PROP_FPS) or float(self.config.fps)
        return float(self.config.fps)

    def get_resolution(self) -> tuple:
        with self.lock:
            if self.capture:
                w = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
                return (w, h)
        return (self.config.width, self.config.height)


# =============================================================================
# DÉTECTION DE MOUVEMENT
# =============================================================================

class MotionDetector:
    """Détecte les mouvements sur un flux vidéo."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.background = None
        self.history = collections.deque(maxlen=10)
        self.last_motion_time = 0.0
        self.cooldown_until = 0.0
        self.frame_count = 0
        self.lock = threading.Lock()

    def reset(self):
        with self.lock:
            self.background = None
            self.history.clear()
            self.last_motion_time = 0.0
            self.cooldown_until = 0.0
            self.frame_count = 0

    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (MOTION_BLUR_SIZE, MOTION_BLUR_SIZE), 0)
        return gray

    def apply_transforms(self, frame: np.ndarray) -> np.ndarray:
        if self.config.flip_horizontal:
            frame = cv2.flip(frame, 1)
        if self.config.flip_vertical:
            frame = cv2.flip(frame, 0)
        if self.config.rotate_90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif self.config.rotate_180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif self.config.rotate_270:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return frame

    def detect(self, frame: np.ndarray) -> tuple:
        with self.lock:
            self.frame_count += 1
            frame = self.apply_transforms(frame)
            gray = self.preprocess(frame)

            if self.background is None:
                self.background = gray.copy().astype("float32")
                return frame, []

            cv2.accumulateWeighted(gray, self.background, 0.5)
            delta = cv2.absdiff(gray, cv2.convertScaleAbs(self.background))
            thresh = cv2.threshold(delta, self.config.motion_threshold, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)

            # Gestion des zones
            mask = thresh.copy()
            h, w = mask.shape[:2]
            if self.config.detection_zones:
                zone_mask = np.zeros_like(mask)
                for zone in self.config.detection_zones:
                    x1, y1, x2, y2 = zone
                    cv2.rectangle(zone_mask, (x1, y1), (x2, y2), 255, -1)
                mask = cv2.bitwise_and(mask, zone_mask)
            for zone in self.config.excluded_zones:
                x1, y1, x2, y2 = zone
                cv2.rectangle(mask, (x1, y1), (x2, y2), 0, -1)

            contours = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours = imutils.grab_contours(contours)

            detections = []
            now = time.time()
            if now < self.cooldown_until:
                return frame, detections

            for contour in contours:
                area = cv2.contourArea(contour)
                if area < self.config.motion_contour_area:
                    continue
                M = cv2.moments(contour)
                cx = int(M["m10"] / M["m00"]) if M["m00"] else 0
                cy = int(M["m01"] / M["m00"]) if M["m00"] else 0
                detections.append({"area": area, "centroid": (cx, cy), "contour": contour})

            if detections:
                self.last_motion_time = now
                self.cooldown_until = now + MOTION_COOLDOWN_SECONDS

            return frame, detections


# =============================================================================
# ENREGISTREMENT VIDÉO
# =============================================================================

class VideoRecorder:
    """Enregistre les segments vidéo autour des événements."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.writer = None
        self.state = RecordingState.STOPPED
        self.lock = threading.Lock()
        self.filepath = ""
        self.segment_start = 0.0
        self.frame_size = (config.width, config.height)
        self.codec = cv2.VideoWriter_fourcc(*"XVID")
        self.pending_clips = []

    def start(self, frame: np.ndarray) -> bool:
        with self.lock:
            if self.state == RecordingState.RECORDING:
                return True
            if frame is None or frame.size == 0:
                return False
            h, w = frame.shape[:2]
            self.frame_size = (w, h)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.filepath = os.path.join("recordings", f"event_{timestamp}.avi")
            try:
                self.writer = cv2.VideoWriter(self.filepath, self.codec, self.config.fps, self.frame_size)
                if not self.writer.isOpened():
                    raise RuntimeError("VideoWriter non ouvert")
                self.state = RecordingState.RECORDING
                self.segment_start = time.time()
                logger.info("Enregistrement démarré : %s", self.filepath)
                return True
            except Exception as exc:
                logger.error("Erreur démarrage enregistrement : %s", exc)
                self.state = RecordingState.STOPPED
                return False

    def write(self, frame: np.ndarray) -> bool:
        with self.lock:
            if self.state != RecordingState.RECORDING or self.writer is None:
                return False
            if frame.shape[:2][::-1] != self.frame_size:
                frame = cv2.resize(frame, self.frame_size)
            try:
                self.writer.write(frame)
                return True
            except Exception as exc:
                logger.error("Erreur écriture frame : %s", exc)
                return False

    def stop(self) -> str:
        with self.lock:
            if self.state != RecordingState.RECORDING:
                return ""
            try:
                self.writer.release()
            except Exception as exc:
                logger.warning("Erreur arrêt enregistrement : %s", exc)
            self.state = RecordingState.STOPPED
            self.writer = None
            path = self.filepath
            self.filepath = ""
            logger.info("Enregistrement arrêté : %s", path)
            return path

    def is_recording(self) -> bool:
        with self.lock:
            return self.state == RecordingState.RECORDING


# =============================================================================
# ALERTES
# =============================================================================

class AlertManager:
    """Gère les alertes sonores et distantes."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.last_alert_time = 0.0
        self.min_interval = 10.0
        self.lock = threading.Lock()

    def trigger(self, event: MotionEvent, message: str = ""):
        with self.lock:
            now = time.time()
            if now - self.last_alert_time < self.min_interval:
                return
            self.last_alert_time = now

        logger.warning("ALERTE MOUVEMENT : %s", message or "Mouvement détecté")

        if self.config.alert_sound:
            self._play_sound()

        if self.config.alert_telegram_token and self.config.alert_telegram_chat_id:
            threading.Thread(
                target=self._send_telegram,
                args=(message or "Mouvement détecté", event.image_path),
                daemon=True,
            ).start()

        if self.config.alert_webhook_url:
            threading.Thread(
                target=self._send_webhook,
                args=(message or "Mouvement détecté", event),
                daemon=True,
            ).start()

    def _play_sound(self):
        system = platform.system()
        try:
            if system == "Windows":
                import winsound
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            elif system == "Darwin":
                subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], check=False)
            else:
                subprocess.run(["paplay", "/usr/share/sounds/freedesktop/stereo/alarm.oga"], check=False)
        except Exception as exc:
            logger.debug("Son non joué : %s", exc)

    def _send_telegram(self, message: str, image_path: str):
        try:
            import requests
            url = f"https://api.telegram.org/bot{self.config.alert_telegram_token}/sendMessage"
            payload = {"chat_id": self.config.alert_telegram_chat_id, "text": message}
            requests.post(url, data=payload, timeout=10)
        except Exception as exc:
            logger.error("Erreur envoi Telegram : %s", exc)

    def _send_webhook(self, message: str, event: MotionEvent):
        try:
            import requests
            payload = {
                "app": APP_NAME,
                "message": message,
                "timestamp": event.timestamp,
                "level": event.level.name,
                "area": event.contour_area,
            }
            requests.post(self.config.alert_webhook_url, json=payload, timeout=10)
        except Exception as exc:
            logger.error("Erreur envoi webhook : %s", exc)


# =============================================================================
# SERVEUR WEB DE CONTRÔLE
# =============================================================================

class SimpleWebServer(threading.Thread):
    """Mini serveur HTTP pour état et snapshots."""

    def __init__(self, port: int, app_state: "AppState"):
        super().__init__(daemon=True)
        self.port = port
        self.app_state = app_state
        self.server_socket = None
        self.running = False

    def run(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.app_state.config.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            logger.info("Serveur web de contrôle démarré sur le port %d", self.port)
            while self.running:
                try:
                    client, addr = self.server_socket.accept()
                    threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
                except OSError:
                    break
        except Exception as exc:
            logger.error("Erreur serveur web : %s", exc)

    def _handle_client(self, client: socket.socket):
        try:
            request = client.recv(4096).decode("utf-8", errors="ignore")
            lines = request.splitlines()
            if not lines:
                return
            path = lines[0].split()[1] if len(lines[0].split()) > 1 else "/"

            if path == "/snapshot.jpg":
                self._send_snapshot(client)
            elif path == "/status.json":
                self._send_status(client)
            elif path == "/":
                self._send_dashboard(client)
            else:
                self._send_404(client)
        except Exception as exc:
            logger.warning("Erreur client web : %s", exc)
        finally:
            try:
                client.close()
            except Exception:
                pass

    def _send_snapshot(self, client: socket.socket):
        frame = self.app_state.latest_frame
        if frame is None:
            self._send_404(client)
            return
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            self._send_404(client)
            return
        data = buf.tobytes()
        headers = [
            "HTTP/1.1 200 OK",
            "Content-Type: image/jpeg",
            f"Content-Length: {len(data)}",
            "Connection: close",
            "",
            "",
        ]
        client.sendall("\r\n".join(headers).encode() + data)

    def _send_status(self, client: socket.socket):
        status = {
            "app": APP_NAME,
            "version": APP_VERSION,
            "connected": self.app_state.video_source.is_open(),
            "state": self.app_state.video_source.state.name,
            "frames_received": self.app_state.video_source.frames_received,
            "motion_events_total": self.app_state.motion_events_count,
            "recording": self.app_state.recorder.is_recording(),
            "timestamp": time.time(),
        }
        body = json.dumps(status, indent=2).encode("utf-8")
        headers = [
            "HTTP/1.1 200 OK",
            "Content-Type: application/json",
            f"Content-Length: {len(body)}",
            "Connection: close",
            "",
            "",
        ]
        client.sendall("\r\n".join(headers).encode() + body)

    def _send_dashboard(self, client: socket.socket):
        ip = get_local_ip()
        html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8">
<title>{APP_NAME} Dashboard</title>
<style>
body{{font-family:Arial,sans-serif;background:#121212;color:#eee;text-align:center}}
h1{{color:#32CD32}} img{{max-width:90%;border:4px solid #32CD32;border-radius:8px}}
.status{{margin:20px;font-size:1.2rem}} .green{{color:#32CD32}} .red{{color:#DC143C}}
</style></head><body>
<h1>{APP_NAME}</h1>
<img id="live" src="/snapshot.jpg" alt="live">
<div class="status" id="status">Chargement...</div>
<script>
setInterval(()=>{{document.getElementById('live').src='/snapshot.jpg?t='+Date.now()}},1000);
setInterval(async()=>{{let r=await fetch('/status.json');let j=await r.json();
document.getElementById('status').innerHTML='Connecté: '+j.connected+' | Images: '+j.frames_received+' | Mouvements: '+j.motion_events_total;
}},1000);
</script></body></html>"""
        body = html.encode("utf-8")
        headers = [
            "HTTP/1.1 200 OK",
            "Content-Type: text/html; charset=utf-8",
            f"Content-Length: {len(body)}",
            "Connection: close",
            "",
            "",
        ]
        client.sendall("\r\n".join(headers).encode() + body)

    def _send_404(self, client: socket.socket):
        body = b"Not Found"
        headers = [
            "HTTP/1.1 404 Not Found",
            "Content-Type: text/plain",
            f"Content-Length: {len(body)}",
            "Connection: close",
            "",
            "",
        ]
        client.sendall("\r\n".join(headers).encode() + body)

    def stop(self):
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass


# =============================================================================
# ÉTAT GLOBAL
# =============================================================================

class AppState:
    """Regroupe les composants et l'état global de l'application."""

    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()
        self.db = DatabaseManager()
        self.video_source = VideoStreamSource(self.config)
        self.motion_detector = MotionDetector(self.config)
        self.recorder = VideoRecorder(self.config)
        self.alert_manager = AlertManager(self.config)
        self.web_server = SimpleWebServer(self.config.web_port, self)
        self.latest_frame = None
        self.latest_motion_frame = None
        self.display_frame = None
        self.motion_events_count = 0
        self.session_id = None
        self.running = False
        self.lock = threading.RLock()
        self.event_callbacks = []
        self.frame_callbacks = []

    def register_event_callback(self, callback):
        self.event_callbacks.append(callback)

    def register_frame_callback(self, callback):
        self.frame_callbacks.append(callback)

    def notify_event(self, event: MotionEvent):
        for cb in self.event_callbacks:
            try:
                cb(event)
            except Exception as exc:
                logger.error("Erreur callback événement : %s", exc)

    def notify_frame(self, frame: np.ndarray):
        for cb in self.frame_callbacks:
            try:
                cb(frame)
            except Exception as exc:
                logger.error("Erreur callback frame : %s", exc)

    def update_config(self, new_config: AppConfig):
        self.config = new_config
        self.video_source.config = new_config
        self.motion_detector.config = new_config
        self.recorder.config = new_config
        self.alert_manager.config = new_config
        self.config_manager.save(new_config)


# =============================================================================
# MOTEUR PRINCIPAL
# =============================================================================

class SurveillanceEngine(threading.Thread):
    """Boucle principale de capture, détection, enregistrement et alertes."""

    def __init__(self, app_state: AppState):
        super().__init__(daemon=True, name="SurveillanceEngine")
        self.app_state = app_state
        self._stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.frame_interval = 1.0 / max(app_state.config.fps, 1)
        self.recording_until = 0.0

    def stop(self):
        self._stop_event.set()

    def pause(self):
        self.pause_event.set()

    def resume(self):
        self.pause_event.clear()

    def is_paused(self) -> bool:
        return self.pause_event.is_set()

    def run(self):
        app = self.app_state
        app.running = True
        app.session_id = app.db.start_session()
        logger.info("Moteur de surveillance démarré (session %d)", app.session_id)

        while not self._stop_event.is_set():
            if self.pause_event.is_set():
                time.sleep(0.2)
                continue

            if not app.video_source.is_open():
                app.video_source.open()
                if not app.video_source.is_open():
                    if app.config.auto_reconnect:
                        app.video_source.state = ConnectionState.RECONNECTING
                        time.sleep(app.config.reconnect_delay_seconds)
                        continue
                    else:
                        break

            ok, frame = app.video_source.read()
            if not ok or frame is None:
                time.sleep(0.05)
                continue

            processed, detections = app.motion_detector.detect(frame)
            app.latest_frame = processed.copy()

            # Overlay
            processed = self._apply_overlays(processed)
            app.display_frame = processed.copy()
            app.notify_frame(processed)

            # Enregistrement continu et événement
            if app.config.enable_recording:
                if detections:
                    self.recording_until = time.time() + MOTION_HISTORY_SECONDS + 1.0
                    if not app.recorder.is_recording():
                        app.recorder.start(processed)
                if app.recorder.is_recording():
                    app.recorder.write(processed)
                    if time.time() > self.recording_until:
                        clip_path = app.recorder.stop()
                        if clip_path:
                            app.db.insert_event(
                                MotionEvent(
                                    timestamp=time.time(),
                                    level=AlertLevel.WARNING,
                                    contour_area=0,
                                    centroid=None,
                                    frame_number=app.motion_detector.frame_count,
                                    video_clip_path=clip_path,
                                ),
                                notes="Fin de clip",
                            )

            # Détection mouvement
            if detections and app.config.enable_motion:
                biggest = max(detections, key=lambda d: d["area"])
                event = MotionEvent(
                    timestamp=time.time(),
                    level=AlertLevel.WARNING,
                    contour_area=biggest["area"],
                    centroid=biggest["centroid"],
                    frame_number=app.motion_detector.frame_count,
                )
                event.image_path = self._save_snapshot(processed, prefix="motion_")
                event.video_clip_path = app.recorder.filepath if app.recorder.is_recording() else ""
                app.motion_events_count += 1
                app.db.insert_event(event, notes="Mouvement détecté")
                app.notify_event(event)
                if app.config.enable_alerts:
                    app.alert_manager.trigger(event, "Mouvement détecté par Convertiseur_Tel_En_Cam")
                app.latest_motion_frame = processed.copy()

            self._cleanup_old_files()
            time.sleep(self.frame_interval)

        # Fermeture propre
        if app.recorder.is_recording():
            app.recorder.stop()
        app.video_source.release()
        app.db.end_session(
            app.session_id,
            app.video_source.frames_received,
            app.motion_events_count,
            0,
        )
        app.running = False
        logger.info("Moteur de surveillance arrêté.")

    def _apply_overlays(self, frame: np.ndarray) -> np.ndarray:
        cfg = self.app_state.config
        if cfg.night_vision:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frame = cv2.applyColorMap(frame, cv2.COLORMAP_JET)
        if cfg.timestamp_overlay:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, ts, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        if cfg.watermark_text:
            cv2.putText(frame, cfg.watermark_text, (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        if self.app_state.recorder.is_recording():
            cv2.circle(frame, (frame.shape[1] - 30, 30), 10, (0, 0, 255), -1)
            cv2.putText(frame, "REC", (frame.shape[1] - 80, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return frame

    def _save_snapshot(self, frame: np.ndarray, prefix: str = "snap_") -> str:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = os.path.join("snapshots", f"{prefix}{ts}.jpg")
        try:
            cv2.imwrite(filename, frame)
        except Exception as exc:
            logger.error("Erreur sauvegarde snapshot : %s", exc)
        return filename

    def _cleanup_old_files(self):
        try:
            now = time.time()
            for folder, max_age_days, max_files in [
                ("recordings", RECORDING_MAX_AGE_DAYS, RECORDING_MAX_FILES),
                ("snapshots", RECORDING_MAX_AGE_DAYS, SNAPSHOT_MAX_FILES),
            ]:
                path = Path(folder)
                if not path.exists():
                    continue
                files = sorted(path.iterdir(), key=lambda p: p.stat().st_mtime)
                for f in files:
                    if now - f.stat().st_mtime > max_age_days * 86400:
                        try:
                            f.unlink()
                        except Exception:
                            pass
                if len(files) > max_files:
                    for f in files[: len(files) - max_files]:
                        try:
                            f.unlink()
                        except Exception:
                            pass
        except Exception as exc:
            logger.debug("Nettoyage fichiers : %s", exc)


# =============================================================================
# INTERFACE GRAPHIQUE TKINTER
# =============================================================================

class ConvertiseurTelEnCamGUI(tk.Tk):
    """Interface graphique principale vert/rouge."""

    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.engine = None
        self.title(APP_TITLE)
        self.geometry("1400x900")
        self.configure(bg=COLORS["bg_dark"])
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.style = ttk.Style(self)
        self._configure_styles()
        self._build_menu()
        self._build_layout()
        self._bind_events()
        self._update_loop_id = None
        self._start_update_loop()
        self.log("Application démarrée. Configurez la source puis cliquez sur Connexion.")
        logger.info("Interface graphique initialisée.")

    def _configure_styles(self):
        self.style.theme_use("clam")
        self.style.configure("TFrame", background=COLORS["bg_dark"])
        self.style.configure(
            "TButton",
            font=("Segoe UI", 10, "bold"),
            foreground=COLORS["white"],
            background=COLORS["green_medium"],
            borderwidth=0,
            relief="flat",
        )
        self.style.map(
            "TButton",
            background=[("active", COLORS["green_light"]), ("pressed", COLORS["green_dark"])],
        )
        self.style.configure(
            "Red.TButton",
            background=COLORS["red_medium"],
        )
        self.style.map(
            "Red.TButton",
            background=[("active", COLORS["red_light"]), ("pressed", COLORS["red_dark"])],
        )
        self.style.configure(
            "TLabel",
            background=COLORS["bg_dark"],
            foreground=COLORS["white"],
            font=("Segoe UI", 10),
        )
        self.style.configure(
            "Title.TLabel",
            foreground=COLORS["green_light"],
            font=("Segoe UI", 18, "bold"),
        )
        self.style.configure(
            "Status.TLabel",
            font=("Segoe UI", 12, "bold"),
        )
        self.style.configure(
            "TEntry",
            fieldbackground=COLORS["gray_dark"],
            foreground=COLORS["white"],
            insertcolor=COLORS["white"],
        )
        self.style.configure(
            "TCheckbutton",
            background=COLORS["bg_dark"],
            foreground=COLORS["white"],
        )

    def _build_menu(self):
        menubar = tk.Menu(self, bg=COLORS["bg_dark"], fg=COLORS["white"], activebackground=COLORS["green_dark"])
        file_menu = tk.Menu(menubar, tearoff=0, bg=COLORS["gray_dark"], fg=COLORS["white"])
        file_menu.add_command(label="Sauvegarder la configuration", command=self.save_config)
        file_menu.add_command(label="Charger la configuration", command=self.load_config)
        file_menu.add_separator()
        file_menu.add_command(label="Exporter les événements CSV", command=self.export_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Quitter", command=self.on_close)
        menubar.add_cascade(label="Fichier", menu=file_menu)

        tools_menu = tk.Menu(menubar, tearoff=0, bg=COLORS["gray_dark"], fg=COLORS["white"])
        tools_menu.add_command(label="Test de connexion", command=self.test_connection)
        tools_menu.add_command(label="Scanner le réseau", command=self.scan_network)
        tools_menu.add_command(label="Prendre un snapshot", command=self.take_snapshot)
        menubar.add_cascade(label="Outils", menu=tools_menu)

        help_menu = tk.Menu(menubar, tearoff=0, bg=COLORS["gray_dark"], fg=COLORS["white"])
        help_menu.add_command(label="Documentation", command=self.show_docs)
        help_menu.add_command(label="À propos", command=self.show_about)
        menubar.add_cascade(label="Aide", menu=help_menu)
        self.config(menu=menubar)

    def _build_layout(self):
        # Barre supérieure
        self.top_frame = ttk.Frame(self, padding=10)
        self.top_frame.pack(fill=tk.X)
        ttk.Label(self.top_frame, text=APP_TITLE, style="Title.TLabel").pack(side=tk.LEFT)
        self.status_label = ttk.Label(
            self.top_frame,
            text="● Déconnecté",
            style="Status.TLabel",
            foreground=COLORS["red_medium"],
        )
        self.status_label.pack(side=tk.RIGHT)

        # Panneau principal
        self.paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Gauche : vidéo
        self.video_frame = ttk.Frame(self.paned, relief="groove", borderwidth=2)
        self.paned.add(self.video_frame, weight=3)
        self.canvas = tk.Canvas(
            self.video_frame,
            bg=COLORS["black"],
            highlightthickness=2,
            highlightbackground=COLORS["green_dark"],
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        # Droite : contrôles
        self.right_frame = ttk.Frame(self.paned, padding=10)
        self.paned.add(self.right_frame, weight=1)
        self._build_controls(self.right_frame)

        # Bas : log
        self.log_frame = ttk.Frame(self, padding=5)
        self.log_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.log_text = scrolledtext.ScrolledText(
            self.log_frame,
            height=8,
            bg=COLORS["black"],
            fg=COLORS["green_light"],
            insertbackground=COLORS["green_light"],
            font=("Consolas", 9),
            state=tk.DISABLED,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _build_controls(self, parent):
        # Section source
        source_lab = ttk.Label(parent, text="Source vidéo", font=("Segoe UI", 12, "bold"), foreground=COLORS["green_light"])
        source_lab.pack(anchor=tk.W, pady=(0, 5))
        self._build_labeled_entry(parent, "IP Téléphone", "phone_ip")
        self._build_labeled_entry(parent, "Port", "phone_port")
        self._build_labeled_entry(parent, "Chemin flux", "stream_path")
        self._build_labeled_entry(parent, "Utilisateur", "username")
        self._build_labeled_entry(parent, "Mot de passe", "password", show="*")

        # Boutons connexion
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=10)
        self.connect_btn = ttk.Button(btn_frame, text="Connexion", command=self.toggle_connection)
        self.connect_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.record_btn = ttk.Button(btn_frame, text="Enregistrer", command=self.toggle_recording)
        self.record_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # Options
        opts_frame = ttk.LabelFrame(parent, text="Options", padding=5)
        opts_frame.pack(fill=tk.X, pady=5)
        self.motion_var = tk.BooleanVar(value=self.app_state.config.enable_motion)
        ttk.Checkbutton(opts_frame, text="Détection mouvement", variable=self.motion_var).pack(anchor=tk.W)
        self.alert_var = tk.BooleanVar(value=self.app_state.config.enable_alerts)
        ttk.Checkbutton(opts_frame, text="Alertes", variable=self.alert_var).pack(anchor=tk.W)
        self.night_var = tk.BooleanVar(value=self.app_state.config.night_vision)
        ttk.Checkbutton(opts_frame, text="Vision nocturne", variable=self.night_var).pack(anchor=tk.W)
        self.timestamp_var = tk.BooleanVar(value=self.app_state.config.timestamp_overlay)
        ttk.Checkbutton(opts_frame, text="Horodatage", variable=self.timestamp_var).pack(anchor=tk.W)

        # Stats
        stats_frame = ttk.LabelFrame(parent, text="Statistiques", padding=5)
        stats_frame.pack(fill=tk.X, pady=5)
        self.frames_label = ttk.Label(stats_frame, text="Images reçues : 0")
        self.frames_label.pack(anchor=tk.W)
        self.motion_label = ttk.Label(stats_frame, text="Mouvements : 0")
        self.motion_label.pack(anchor=tk.W)
        self.fps_label = ttk.Label(stats_frame, text="FPS : 0")
        self.fps_label.pack(anchor=tk.W)

        # Alertes
        alert_frame = ttk.LabelFrame(parent, text="Alertes", padding=5)
        alert_frame.pack(fill=tk.X, pady=5)
        self._build_labeled_entry(alert_frame, "Webhook URL", "alert_webhook_url")
        self._build_labeled_entry(alert_frame, "Telegram Token", "alert_telegram_token")
        self._build_labeled_entry(alert_frame, "Telegram Chat ID", "alert_telegram_chat_id")

    def _build_labeled_entry(self, parent, label: str, attr: str, show: str = None):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=2)
        ttk.Label(frame, text=label, width=16, anchor=tk.W).pack(side=tk.LEFT)
        var = tk.StringVar(value=getattr(self.app_state.config, attr, ""))
        entry = ttk.Entry(frame, textvariable=var, show=show or "")
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        setattr(self, f"{attr}_var", var)

    def _bind_events(self):
        self.app_state.register_frame_callback(self._on_new_frame)
        self.app_state.register_event_callback(self._on_motion_event)

    def _on_canvas_resize(self, event):
        pass

    def _on_new_frame(self, frame: np.ndarray):
        self.latest_frame = frame

    def _on_motion_event(self, event: MotionEvent):
        self.log(f"Mouvement détecté (aire={event.contour_area:.0f}) à {event.centroid}")

    def _start_update_loop(self):
        self._update_gui()

    def _update_gui(self):
        try:
            # Mise à jour image
            if hasattr(self, "latest_frame") and self.latest_frame is not None:
                canvas_w = self.canvas.winfo_width()
                canvas_h = self.canvas.winfo_height()
                if canvas_w > 1 and canvas_h > 1:
                    display = resize_keep_aspect(self.latest_frame, canvas_w, canvas_h)
                    rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
                    im = tk.PhotoImage(master=self.canvas, data=cv2.imencode(".ppm", rgb)[1].tobytes())
                    self.canvas.create_image(0, 0, anchor=tk.NW, image=im)
                    self.canvas.image = im

            # Mise à jour statut
            state = self.app_state.video_source.state
            if state == ConnectionState.CONNECTED:
                self.status_label.config(text="● Connecté", foreground=COLORS["green_medium"])
            elif state == ConnectionState.CONNECTING:
                self.status_label.config(text="● Connexion...", foreground=COLORS["orange"])
            elif state == ConnectionState.RECONNECTING:
                self.status_label.config(text="● Reconnexion...", foreground=COLORS["yellow"])
            else:
                self.status_label.config(text="● Déconnecté", foreground=COLORS["red_medium"])

            # Stats
            src = self.app_state.video_source
            self.frames_label.config(text=f"Images reçues : {src.frames_received}")
            self.motion_label.config(text=f"Mouvements : {self.app_state.motion_events_count}")
            elapsed = time.time() - src.start_time if src.start_time else 1
            fps = src.frames_received / elapsed if elapsed > 0 else 0
            self.fps_label.config(text=f"FPS : {fps:.1f}")
        except Exception as exc:
            logger.error("Erreur mise à jour GUI : %s", exc)
        self._update_loop_id = self.after(50, self._update_gui)

    def _sync_config_from_gui(self):
        cfg = self.app_state.config
        cfg.phone_ip = self.phone_ip_var.get()
        try:
            cfg.phone_port = int(self.phone_port_var.get())
        except ValueError:
            pass
        cfg.stream_path = self.stream_path_var.get()
        cfg.username = self.username_var.get()
        cfg.password = self.password_var.get()
        cfg.enable_motion = self.motion_var.get()
        cfg.enable_alerts = self.alert_var.get()
        cfg.night_vision = self.night_var.get()
        cfg.timestamp_overlay = self.timestamp_var.get()
        cfg.alert_webhook_url = self.alert_webhook_url_var.get()
        cfg.alert_telegram_token = self.alert_telegram_token_var.get()
        cfg.alert_telegram_chat_id = self.alert_telegram_chat_id_var.get()
        self.app_state.update_config(cfg)

    def toggle_connection(self):
        if self.engine and self.engine.is_alive():
            self.engine.stop()
            self.connect_btn.config(text="Connexion")
            self.log("Déconnexion demandée.")
        else:
            self._sync_config_from_gui()
            if not self.app_state.video_source.is_open():
                if not self.app_state.video_source.open():
                    messagebox.showerror("Erreur", f"Connexion impossible : {self.app_state.video_source.last_error}")
                    return
            self.engine = SurveillanceEngine(self.app_state)
            self.engine.start()
            self.app_state.web_server.start()
            self.connect_btn.config(text="Déconnexion")
            self.log(f"Connexion démarrée vers {self.app_state.config.phone_ip}:{self.app_state.config.phone_port}")

    def toggle_recording(self):
        cfg = self.app_state.config
        cfg.enable_recording = not cfg.enable_recording
        self.app_state.update_config(cfg)
        self.record_btn.config(text="Arrêter enreg." if cfg.enable_recording else "Enregistrer")
        self.log(f"Enregistrement {'activé' if cfg.enable_recording else 'désactivé'}.")

    def take_snapshot(self):
        frame = self.app_state.latest_frame
        if frame is None:
            messagebox.showwarning("Snapshot", "Aucune image disponible.")
            return
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join("snapshots", f"manual_{ts}.jpg")
        cv2.imwrite(path, frame)
        self.log(f"Snapshot sauvegardé : {path}")

    def test_connection(self):
        self._sync_config_from_gui()
        vs = VideoStreamSource(self.app_state.config)
        ok = vs.open()
        if ok:
            vs.release()
            messagebox.showinfo("Test", "Connexion réussie !")
        else:
            messagebox.showerror("Test", f"Échec : {vs.last_error}")

    def scan_network(self):
        base = simpledialog.askstring("Scanner", "Base réseau (ex: 192.168.1):", initialvalue="192.168.1")
        if not base:
            return
        found = []
        for i in range(1, 255):
            ip = f"{base}.{i}"
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.3)
                result = sock.connect_ex((ip, self.app_state.config.phone_port))
                sock.close()
                if result == 0:
                    found.append(ip)
            except Exception:
                pass
        if found:
            messagebox.showinfo("Résultat", "IP trouvées :\n" + "\n".join(found[:20]))
        else:
            messagebox.showinfo("Résultat", "Aucune IP trouvée.")

    def save_config(self):
        self._sync_config_from_gui()
        if self.app_state.config_manager.save(self.app_state.config):
            self.log("Configuration sauvegardée.")
        else:
            messagebox.showerror("Erreur", "Impossible de sauvegarder la configuration.")

    def load_config(self):
        cfg = self.app_state.config_manager.load()
        self.app_state.update_config(cfg)
        self.phone_ip_var.set(cfg.phone_ip)
        self.phone_port_var.set(str(cfg.phone_port))
        self.stream_path_var.set(cfg.stream_path)
        self.username_var.set(cfg.username)
        self.password_var.set(cfg.password)
        self.motion_var.set(cfg.enable_motion)
        self.alert_var.set(cfg.enable_alerts)
        self.night_var.set(cfg.night_vision)
        self.timestamp_var.set(cfg.timestamp_overlay)
        self.alert_webhook_url_var.set(cfg.alert_webhook_url)
        self.alert_telegram_token_var.set(cfg.alert_telegram_token)
        self.alert_telegram_chat_id_var.set(cfg.alert_telegram_chat_id)
        self.log("Configuration chargée.")

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Tous fichiers", "*.*")],
        )
        if path:
            if self.app_state.db.export_csv(path):
                self.log(f"Événements exportés vers {path}")
            else:
                messagebox.showwarning("Export", "Aucun événement à exporter.")

    def show_docs(self):
        docs = textwrap.dedent(
            """
            Convertiseur_Tel_En_Cam — Documentation rapide

            1. Installez une application IP Webcam sur votre téléphone (ex: IP Webcam).
            2. Connectez le téléphone au même Wi-Fi que ce PC.
            3. Notez l'IP et le port affichés sur le téléphone.
            4. Saisissez ces informations dans l'interface puis cliquez sur Connexion.
            5. Le flux apparaît dans la fenêtre. La détection de mouvement est active.
            6. Les enregistrements et snapshots sont dans les dossiers recordings/ et snapshots/.
            7. Le dashboard web est accessible via http://<IP_PC>:8090/.
            """
        )
        messagebox.showinfo("Documentation", docs)

    def show_about(self):
        messagebox.showinfo(
            "À propos",
            f"{APP_NAME}\nVersion {APP_VERSION}\nAuteur {APP_AUTHOR}\nLicence {APP_LICENSE}",
        )

    def log(self, message: str):
        self.log_text.config(state=tk.NORMAL)
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{ts}] {message}\n")
        self.log_text.see(tk.END)
        max_lines = self.app_state.config.max_log_lines
        count = int(self.log_text.index("end-1c").split(".")[0])
        if count > max_lines:
            self.log_text.delete("1.0", f"{count - max_lines}.0")
        self.log_text.config(state=tk.DISABLED)

    def on_close(self):
        if self.engine and self.engine.is_alive():
            self.engine.stop()
            self.engine.join(timeout=2)
        self.app_state.web_server.stop()
        self.app_state.video_source.release()
        if self._update_loop_id:
            self.after_cancel(self._update_loop_id)
        self.destroy()


# =============================================================================
# POINT D'ENTRÉE
# =============================================================================

def main():
    ensure_directories()
    logger.info("Démarrage de %s v%s", APP_NAME, APP_VERSION)
    app_state = AppState()
    app = ConvertiseurTelEnCamGUI(app_state)
    app.mainloop()


if __name__ == "__main__":
    main()
