# Firebase Push Notifications Setup

This guide explains how to configure Firebase Cloud Messaging (FCM) for the Abound NextGen E Hub PWA.

## Prerequisites

- Firebase project
- Web app added to the Firebase project

## 1. Firebase Console Setup

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create or select a project
3. Add a **Web app** (</> icon) and note the config values
4. In **Project Settings** → **Cloud Messaging**:
   - Enable **Cloud Messaging API (Legacy)** if needed
   - Under **Web configuration**, generate a **Key pair** (VAPID key) for Web Push
5. In **Project Settings** → **Service accounts**:
   - Generate a new private key (download JSON)
   - Save the JSON file securely (e.g. `firebase-service-account.json`)

## 2. Environment Variables

Add to your `.env` file:

```env
# Firebase FCM - Push Notifications
FIREBASE_API_KEY=AIzaSyBRUcuYQiW8X6OMMJbli41sXnOTHCkBH6w
FIREBASE_PROJECT_ID=aboundehub-40339
FIREBASE_APP_ID=1:908221804165:web:8f95ce3dfdcc312d7543ec
FIREBASE_MESSAGING_SENDER_ID=908221804165
FIREBASE_VAPID_KEY=BBG_aQ4w8EYwz2py3P6aFKm-dowlYDhu7WT0Uo-ABucMHDeZBGa0K0KD7iGBC2g5C360BBLBDP2tXYIHffW36Pc
FIREBASE_SERVICE_ACCOUNT_PATH=/absolute/path/to/firebase-service-account.json
```

- `FIREBASE_API_KEY`, `FIREBASE_PROJECT_ID`, `FIREBASE_APP_ID`, `FIREBASE_MESSAGING_SENDER_ID`: from the Firebase web app config
- `FIREBASE_VAPID_KEY`: from Cloud Messaging → Web configuration → Key pair
- `FIREBASE_SERVICE_ACCOUNT_PATH`: absolute path to the service account JSON file

## 3. Production Domain

- Set `APP_URL` to your production domain (e.g. `https://your-domain.com`)
- For Web Push `link` in notifications, `APP_URL` must use `https://` in production

## Production Checklist: Push Notifications

When your production HTTPS URL is ready, follow these steps:

### Step 1 — Firebase Console

1. Go to [Firebase Console](https://console.firebase.google.com/) → your project
2. **Project Settings** → **General** → **Your apps**
3. Under your Web app, find **Authorized domains**
4. Add your production domain (e.g. `your-domain.com`) if not already listed

### Step 2 — Update `.env`

Change this line in your `.env` file:

```
# From (development):
APP_URL=http://localhost:5001

# To (production):
APP_URL=https://your-production-domain.com
```

- Use `https://` — push notification links require HTTPS
- Do not add a trailing slash
- Examples: `https://aboundehub.com`, `https://app.yoursite.com`

### Step 3 — Firebase Config (Optional)

If you use a **different Firebase project** for production:

- Create a new Web app in the production Firebase project
- Update these in `.env`:
  - `FIREBASE_API_KEY`
  - `FIREBASE_PROJECT_ID`
  - `FIREBASE_APP_ID`
  - `FIREBASE_MESSAGING_SENDER_ID`
  - `FIREBASE_VAPID_KEY`
- Use the production project's service account JSON for `FIREBASE_SERVICE_ACCOUNT_PATH`

*(If you use the same Firebase project for dev and prod, no changes needed.)*

### Step 4 — Deploy & Restart

1. Deploy your app to production
2. Restart the application server so it picks up the new `APP_URL`
3. Ensure the production server can read `FIREBASE_SERVICE_ACCOUNT_PATH` (correct path if different from local)

### Step 5 — Test Push Notifications

1. Open the app in Chrome on desktop or mobile **via your production HTTPS URL**
2. Log in and go to **Notification Settings**
3. Click **Enable Notifications** — you should see the browser permission prompt
4. Send a test notification from **Admin → Notification Center → Specific User** (select yourself)

### Summary of Files to Edit

| Item | Location | Change |
|------|----------|--------|
| App URL | `.env` | `APP_URL=https://your-domain.com` |
| Firebase domains | Firebase Console | Add production domain to Authorized domains |
| Firebase config | `.env` | Only if using a different Firebase project |

## 4. Usage

- **Users**: After login, click **Enable Notifications** on the Dashboard or go to **Notification Settings** in the sidebar
- **Events**: Push notifications are sent for:
  - Order Placed
  - Order Shipped
- **Admin announcements**: Use `send_push_notification(user_ids, title, body, click_action)` from backend code

## 5. Sending Custom Notifications

Example from Python (e.g. in a management command or admin view):

```python
from app import send_push_notification

# Notify specific users
send_push_notification([user_id], "New Product Launch", "Check out our latest jewelry!", "/products")

# Admin announcement to many users
user_ids = [u.id for u in User.query.filter_by(user_role='user').all()]
send_push_notification(user_ids, "Announcement", "Important update from Abound.", "/dashboard")
```
