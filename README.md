# Sales Team Portal

A comprehensive web application for managing a sales team with hierarchical structure and automated promotion system.

## Features

- **Agent Authentication**: Secure login system for sales agents
- **Product Catalog**: Display and manage products
- **Team Management**: Agents can onboard new team members under them
- **Automated Hierarchy**: Automatic promotion when an agent reaches 10 team members
- **Dashboard**: Overview of team stats and promotion progress

## Technology Stack

- **Backend**: Python Flask
- **Frontend**: HTML, CSS, JavaScript
- **Database**: SQLite (can be easily switched to PostgreSQL)
- **Authentication**: Session-based authentication

## Installation

1. **Create and use a virtual environment (recommended)**:
```bash
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Or install globally** (if you have write access to site-packages):
```bash
pip install -r requirements.txt
```

3. **Run the application**:
```bash
python app.py
# Or with venv: ./venv/bin/python app.py  (without activating)
```

4. **Initial Setup**:
   - When you first run the app, visit `http://localhost:5001/setup` to create an admin account
   - After setup, use the admin credentials to login at `http://localhost:5001/login`

   **macOS users:** Port 5000 is used by AirPlay Receiver on Monterey and later. This app runs on **port 5001** to avoid conflicts.

## Documentation

- [Firebase push notifications setup](docs/FIREBASE_PUSH_SETUP.md)

## Project Structure

```
Unique_Jewels/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── templates/            # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── setup.html
│   ├── dashboard.html
│   ├── products.html
│   └── my_team.html
├── static/               # Static files
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
└── sales_team.db        # SQLite database (created automatically)
```

## Hierarchy Levels

The system includes the following hierarchy levels:

1. **Sales Agent** (Starting position)
2. **Team Leader** (Requires 10 team members)
3. **Senior Team Leader** (Requires 20 team members)
4. **Manager** (Requires 30 team members)
5. **Senior Manager** (Requires 50 team members)

## Usage

1. **Login**: Access the portal at `http://localhost:5001/login`
2. **Dashboard**: View your team stats and promotion progress
3. **Products**: Browse available products
4. **My Team**: View your team members and onboard new agents
5. **Onboarding**: Click "Onboard New Agent" to add team members

## API Endpoints

- `GET /` - Redirects to dashboard or login
- `GET /login` - Login page
- `POST /login` - Authenticate user
- `GET /logout` - Logout user
- `GET /dashboard` - User dashboard
- `GET /products` - Product catalog
- `GET /my-team` - Team management page
- `POST /onboard` - Onboard new agent
- `GET /api/team-stats` - Get team statistics (JSON)

## Database Schema

- **User**: Stores agent information, hierarchy relationships
- **Product**: Product catalog
- **HierarchyLevel**: Defines promotion levels and requirements

## Security Notes

- Change the `SECRET_KEY` in `app.py` for production
- Use environment variables for sensitive configuration
- Consider using PostgreSQL for production deployments
- Implement password strength requirements
- Add rate limiting for login attempts

## Troubleshooting: What can fail and how to fix it

| Issue | Cause | Fix |
|-------|--------|-----|
| **`pip install` fails with "Operation not permitted"** | Pip tries to install to user site-packages (`~/.local`) and lacks permission | Use a virtual environment: `python3 -m venv venv` then `./venv/bin/pip install -r requirements.txt` |
| **Promotion shows wrong/new position** | After promotion, the in-memory user object wasn’t refreshed from DB | Fixed in code: `db.session.refresh(parent_user)` after `check_and_promote_user()` |
| **App won’t start** | Missing dependencies or wrong Python path | Activate venv (`source venv/bin/activate`) or run with `./venv/bin/python app.py` |
| **Setup page redirects to login** | Database already has users | Normal after first setup; use existing credentials or delete `sales_team.db` in the project root to reset |
| **Page not loading / blank** | Port 5000 used by AirPlay on macOS | App runs on **port 5001**. Use `http://localhost:5001` |

Using the project’s `venv` and running with `./venv/bin/python app.py` (or after `source venv/bin/activate`, `python app.py`) makes the app run successfully.

## Development

To run in development mode:
```bash
export FLASK_ENV=development
python app.py
```

The app will run on `http://localhost:5001` with debug mode enabled.
