# Aetherium Gallery

A web-based application built with Python (FastAPI) to manage, visualize, and categorize AI-generated images, focusing on metadata and creative exploration.

# Project tree structure:

aetherium_gallery/
├── aetherium_gallery/
│ ├── routers/
│ │ ├── **init**.py
│ │ ├── frontend.py
│ │ └── images.py
│ ├── **init**.py
│ ├── config.py
│ ├── crud.py
│ ├── database.py
│ ├── main.py
│ ├── models.py
│ ├── schemas.py
│ └── utils.py
├── static/
│ ├── css/
│ │ └── style.css
│ └── js/
│ └── script.js
├── templates/
│ ├── base.html
│ ├── image.detail.html
│ ├── index.html
│ └── upload.html
├── uploads/
├── .env
├── .gitignore
├── README.md
└── requirements.txt

## Features (Initial Setup)

- **Image Upload:** Upload multiple images via a web form.
- **Gallery View:** Basic grid view displaying thumbnails.
- **Detail View:** View larger image and extracted/stored metadata.
- **Basic Metadata Extraction:** Attempts to parse dimensions and basic Stable Diffusion parameters from PNG info.
- **Thumbnail Generation:** Automatically creates thumbnails for faster gallery loading.
- **File Storage:** Stores images locally in an `uploads` directory.
- **Database:** Uses SQLAlchemy (async) with SQLite (default) to store image information.

## Setup and Running

1.  **Clone the Repository:**

    ```bash
    git clone <your-repository-url>
    cd aetherium-gallery
    ```

2.  **Create a Virtual Environment:**

    ```bash
    python -m venv venv
    # On Windows:
    # venv\Scripts\activate
    # On macOS/Linux:
    # source venv/bin/activate
    ```

3.  **Install Dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment:**

    - Copy the `.env.example` file (if you create one) or create `.env` manually.
    - Ensure `DATABASE_URL` and `UPLOAD_FOLDER` are set correctly.
    - **Generate a `SECRET_KEY`**: Run `python -c 'import secrets; print(secrets.token_hex(32))'` and paste the output into `.env`.
    - Make sure the directory specified by `UPLOAD_FOLDER` (default: `uploads`) exists and the application has write permissions to it.

5.  **Run the Database Initialization (First Time):**
    The application attempts to create tables on startup (`init_db` in `database.py` called from `main.py`). Ensure this runs successfully the first time. For production or complex changes, use a migration tool like Alembic.

6.  **Run the Application (Development):**

    ```bash
    uvicorn aetherium_gallery.main:app --reload --host 0.0.0.0 --port 8000
    ```

    - `--reload`: Automatically restarts the server when code changes (for development).
    - `--host 0.0.0.0`: Makes the server accessible on your local network.
    - `--port 8000`: Specifies the port number.

7.  **Access the Application:**
    Open your web browser and navigate to `http://127.0.0.1:8000` or `http://<your-local-ip>:8000`.

## Next Steps & Planned Features

- Implement Tagging system (CRUD, assigning to images).
- Implement Albums/Collections.
- Robust Metadata Parsing (support for more formats, sidecar files).
- Advanced Search & Filtering (by metadata, tags).
- User Ratings & Favorites update via API.
- Batch Operations (tagging, deleting).
- Visual Similarity Search (using CLIP embeddings).
- "Evolution View" for comparing parameter changes.
- Smart Collections based on filters.
- User Authentication (optional).
- Background Task Processing (Celery) for intensive tasks (metadata extraction, embedding generation).
- Improved Frontend (HTMX or a JS framework).
- More sophisticated image editing/preview options.

## Contributing

[Details on how to contribute - if applicable]

## License

[Choose and specify a license, e.g., MIT]
