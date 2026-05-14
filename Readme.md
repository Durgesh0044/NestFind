# NestFind - Real Estate Platform

NestFind is a comprehensive real estate web application built with Flask. It allows users to browse, search, and manage real estate properties efficiently.

## 🚀 Tech Stack
- **Backend:** Python, Flask
- **Database:** PostgreSQL / SQLite (via Flask-SQLAlchemy)
- **Authentication:** Flask-Login
- **Data Processing:** pandas, openpyxl, pdfplumber
- **Frontend:** HTML, CSS, JavaScript (Jinja2 templates)

## 📁 Project Structure
- `app.py`: Entry point for the Flask application.
- `core/`: Contains the core application logic, routes, and application factory (`create_app`).
- `templates/`: Jinja2 HTML templates for the frontend.
- `static/`: Static assets such as CSS, JavaScript, and images.
- `database.db`: SQLite database file (for local development).
- `requirements.txt`: Python dependencies.

## 🛠️ Prerequisites
Ensure you have the following installed:
- Python 3.8+
- pip (Python package installer)

## ⚙️ Installation & Setup

1. **Navigate to the project directory:**
   ```bash
   cd Realestate
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   Create a `.env` file in the root directory (or use the existing one) to define your environment configurations such as secret keys or database connection strings.

## ▶️ Running the Application

Start the Flask development server:
```bash
python app.py
```
The application will be accessible at `http://localhost:5000/` or `http://127.0.0.1:5000/`.
