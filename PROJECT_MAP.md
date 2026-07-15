# Project Map

This document maps the current Flask project structure, routes, models, helpers, templates, integrations, and major workflow call graphs. It is documentation only.

## High-Level Architecture

- Runtime: Flask application started from `app.py`.
- Database: Flask-SQLAlchemy using SQLite URI `sqlite:///sales_team.db`.
- Auth: session-based login with Werkzeug password hashing.
- UI: Jinja templates under `templates/`, with shared logged-in layout in `templates/base.html` and public layout in `templates/base_public.html`.
- Static assets: CSS, JavaScript, PWA manifest, icons, product images, and APK download under `static/`.
- Integrations:
  - Razorpay Standard Checkout for online payments.
  - Firebase Cloud Messaging for push notifications.
  - Resend API plus legacy SMTP helpers for email.
- Business domains:
  - Sales referral hierarchy.
  - User onboarding and registration.
  - Product catalog and checkout.
  - Orders, shipping, commissions, wallets.
  - Admin and super-admin operations.

## Major Modules

### `app.py`

Main Flask module. Contains:

- Flask app creation and configuration.
- SQLAlchemy initialization.
- Firebase Admin lazy initialization.
- Email helper functions.
- Push notification helper functions.
- Context processors.
- All database model classes.
- Auth decorators.
- Commission and promotion logic.
- All route handlers.
- Manual schema migration/backfill logic.
- App startup and sample product seeding.

### `hierarchy.py`

Sales hierarchy configuration:

- `LEVELS`: ordered sales levels 1 through 10.
- `COMMISSION_BY_LEVEL`: commission percentage for commission-chain level 1 through 10.
- `PROMOTION_DIRECT_COUNT`: direct same-level referral count required for promotion.

### `integrations/resend_email.py`

Resend email API helper:

- `RESEND_API_URL`
- `send_email(to, subject, html)`

### `integrations/razorpay_checkout.py`

Razorpay Standard Checkout helper:

- `get_razorpay_client(key_id, key_secret)`
- `create_razorpay_order(client, amount, currency, receipt)`
- `verify_payment_signature(key_secret, order_id, payment_id, signature)`

### `static/js/razorpay-checkout.js`

Checkout frontend workflow:

- Starts pending app order creation.
- Creates Razorpay order through backend.
- Opens Razorpay checkout modal.
- Sends payment verification request.
- Redirects to order success page.

### `static/js/firebase-notifications.js`

Browser Firebase Cloud Messaging workflow:

- Checks browser support.
- Fetches Firebase config.
- Requests notification permission.
- Registers service worker.
- Gets FCM token.
- Saves/removes device token through backend APIs.

### `static/js/pwa.js`

PWA install and service worker client behavior.

### `static/js/sidebar.js`

Logged-in sidebar toggle and accordion behavior.

### `static/js/main.js`

Shared frontend behavior.

### Scripts

- `scripts/clear_commissions_and_orders.py`: maintenance script for clearing order/commission data.
- `scripts/delete_sales_agents.py`: maintenance script for deleting sales agents.
- `scripts/generate_walkthrough_ppt.py`: generates walkthrough PowerPoint.

### Docs

- `docs/FIREBASE_PUSH_SETUP.md`: Firebase push setup.
- `docs/VIDEO_WALKTHROUGH_SCRIPT.md`: walkthrough script.
- `docs/Abound_NextGen_E-Hub_Walkthrough.pptx`: generated walkthrough deck.

## Database Models

### `User`

Main account and hierarchy model.

Fields:

- `id`
- `username`
- `email`
- `password_hash`
- `full_name`
- `user_level`
- `parent_id`
- `referral_id`
- `created_at`
- `is_active`
- `user_status`
- `is_admin`
- `user_role`
- `phone`
- `address`
- `position`

Relationships:

- `children`: self-referential downline users.
- `parent`: self-referential sponsor/upline.
- Backrefs from `Address`, `DeviceToken`, `Order`, `Wallet`, `ActivityLog`, `Notification`, `Commission`, `PromotionHistory`.

Methods/properties:

- `check_password(password)`
- `get_sales_children()`
- `get_team_count()`
- `get_direct_referrals()`
- `get_all_descendants()`
- `level_name`
- `get_upline_chain(max_levels=10)`
- `get_commission_upline_chain(max_levels=10)`
- `is_super_admin`
- `is_admin_role`
- `is_sales_user`
- `is_user_active`

### `Category`

Product category.

Fields:

- `id`
- `name`
- `created_at`

Relationships:

- `products`

### `Product`

Catalog product.

Fields:

- `id`
- `name`
- `description`
- `price`
- `image_url`
- `category_id`
- `stock_quantity`
- `sku`
- `weight`
- `dimensions`
- `created_at`

Relationships:

- `category`
- `orders`

Properties:

- `is_out_of_stock`

### `Address`

Saved delivery address.

Fields:

- `id`
- `user_id`
- `full_name`
- `phone`
- `street_address`
- `landmark`
- `city`
- `state`
- `pincode`
- `country`
- `is_default`
- `created_at`
- `updated_at`

Relationships:

- `user`

Methods:

- `to_shipping_string()`
- `to_display_lines()`

### `DeviceToken`

Firebase Cloud Messaging token.

Fields:

- `id`
- `user_id`
- `token`
- `created_at`

Relationships:

- `user`

Constraints:

- Unique `(user_id, token)`

### `Order`

Customer order.

Fields:

- `id`
- `user_id`
- `product_id`
- `amount`
- `quantity`
- `shipping_address`
- `shipment_notes`
- `phone`
- `status`
- `payment_status`
- `razorpay_order_id`
- `commission_generated`
- `shipped_at`
- `created_at`

Relationships:

- `user`
- `product`
- `commissions`

### `Wallet`

User commission wallet.

Fields:

- `id`
- `user_id`
- `total_earnings`
- `available_balance`
- `withdrawn_balance`
- `last_updated`

Relationships:

- `user`

### `ActivityLog`

Admin audit trail.

Fields:

- `id`
- `admin_id`
- `action`
- `target_type`
- `target_id`
- `details`
- `created_at`

Relationships:

- `admin`

### `Notification`

Admin-sent notification log.

Fields:

- `id`
- `title`
- `message`
- `audience_type`
- `target_level`
- `delivery_methods`
- `recipient_count`
- `sent_by_admin_id`
- `created_at`

Relationships:

- `sent_by`

### `Commission`

Commission record for an order.

Fields:

- `id`
- `user_id`
- `order_id`
- `commission_amount`
- `commission_percent`
- `commission_level`
- `commission_level_name`
- `status`
- `created_at`

Relationships:

- `user`
- `order`

### `PromotionHistory`

Promotion audit record.

Fields:

- `id`
- `user_id`
- `from_level`
- `to_level`
- `created_at`

Relationships:

- `user`

## Helper Functions

### Configuration and Assets

- `get_firebase_app()`: lazy-initialize Firebase Admin SDK from service account file.
- `get_logo_url()`: locate logo file under `static/images`.
- `get_director_profile_url()`: locate director profile image.
- `get_director_signature_url()`: locate director signature image.
- `inject_globals()`: Jinja context processor adding logo URLs, current user, and admin flags.

### Referral and Hierarchy

- `generate_referral_id()`: generate unique `ABNxxxxx` referral ID.
- `count_direct_at_level(user, level)`: count direct sales children at a specific level.
- `check_and_promote_user(user_id)`: promote sales user when same-level direct referral threshold is met.

### Email

- `send_welcome_email(user)`: sends welcome email through Resend.
- `send_order_notification(order)`: sends new order email to admins through Resend.
- `send_order_confirmation_buyer(order)`: sends buyer order confirmation through Resend.
- `send_order_shipped_buyer(order)`: sends buyer shipped email through Resend.
- `send_order_shipped_admin(order)`: sends shipped notification to admins through SMTP.
- `send_credentials_email(user, password)`: sends generated credentials through SMTP.
- `send_notification_email(to_email, title, message, click_action=None)`: sends notification-center email through SMTP.
- `send_contact_form_email(name, email, subject, message)`: sends contact form email through SMTP.

### Push Notifications

- `send_push_notification(user_ids, title, body, click_action=None, icon=None)`: sends Firebase Cloud Messaging push notification to stored device tokens.

### Auth and Authorization

- `require_admin(f)`: route decorator requiring admin or super admin.
- `require_super_admin(f)`: route decorator requiring super admin.
- `check_user_active()`: `before_request` hook blocking inactive sales users.

### Wallets and Commissions

- `get_or_create_wallet(user_id)`: fetches or initializes wallet.
- `distribute_commission(order)`: distributes paid-order commission up the sponsor chain.
- `reverse_commission(order)`: reverses active commissions for cancelled orders.
- `_clear_order_commissions(order)`: removes active commission records and adjusts wallets before recalculation.
- `recalculate_commissions_for_orders(orders)`: recalculates commissions for paid orders.

### Checkout and Addresses

- `_checkout_user_or_error()`: validates logged-in sales user for checkout APIs.
- `_parse_checkout_shipping(user, product_id, quantity)`: resolves shipping fields from selected or manual address.
- `_maybe_save_checkout_address(user, selected_address_id, form_data=None)`: saves manual checkout address when requested.
- `_validate_address_form(data)`: validates saved address form input.

### Admin and Maintenance

- `log_activity(admin_id, action, target_type=None, target_id=None, details=None)`: queues admin activity log.
- `migrate_db()`: creates/migrates tables and backfills data.
- `has_sales_users()`: checks whether any sales users exist.
- `scan_tree_integrity()`: finds orphan users, circular references, admins in tree, and duplicate referral IDs.
- `_get_notification_recipients(audience_type, target_user_id=None, target_level=None)`: resolves notification audience.
- `_admin_notifications_post()`: validates, sends, and logs admin notification requests.

### Integration Helpers

- `integrations.resend_email.send_email(to, subject, html)`: sends email via Resend REST API.
- `integrations.razorpay_checkout.get_razorpay_client(key_id, key_secret)`: creates Razorpay client.
- `integrations.razorpay_checkout.create_razorpay_order(client, amount, currency, receipt)`: creates Razorpay order.
- `integrations.razorpay_checkout.verify_payment_signature(key_secret, order_id, payment_id, signature)`: verifies Razorpay signature.

## Routes

### PWA and Static App Shell

| Route | Methods | Handler | Purpose |
|---|---:|---|---|
| `/manifest.json` | GET | `pwa_manifest` | Serve PWA manifest. |
| `/service-worker.js` | GET | `pwa_service_worker` | Serve static or Firebase-enabled service worker. |
| `/downloads/abound-ehub.apk` | GET | `download_apk` | Serve APK download. |
| `/offline` | GET | `pwa_offline` | Offline fallback page. |

### Public Pages

| Route | Methods | Handler | Purpose |
|---|---:|---|---|
| `/` | GET | `index` | Public home or logged-in dashboard redirect. |
| `/catalog` | GET | `catalog` | Public product catalog. |
| `/about` | GET | `about` | About page. |
| `/about/director-message` | GET | `director_message` | Director message page. |
| `/contact` | GET, POST | `contact` | Contact form and submission. |
| `/profile` | GET | `profile` | Redirect to dashboard or login. |
| `/faq` | GET | `faq` | FAQ page. |

### Authentication and Setup

| Route | Methods | Handler | Purpose |
|---|---:|---|---|
| `/login` | GET, POST | `login` | User/admin login. |
| `/logout` | GET | `logout` | Clear session. |
| `/register` | GET, POST | `register` | Public referral registration. |
| `/setup` | GET, POST | `setup` | Initial admin setup when no users exist. |
| `/test-send-welcome-email` | GET | `test_send_welcome_email_redirect` | Redirect to email test. |
| `/email-test` | GET, POST | `email_test` | Email test page. |
| `/admin-email-test` | GET, POST | `email_test` | Alternate email test route. |

### Sales User Pages and APIs

| Route | Methods | Handler | Purpose |
|---|---:|---|---|
| `/dashboard` | GET | `dashboard` | Sales user dashboard. |
| `/products` | GET | `products` | Logged-in product list. |
| `/checkout` | GET | `checkout` | Checkout page. |
| `/api/checkout/prepare-pending` | POST | `checkout_prepare_pending` | Create pending app order before Razorpay. |
| `/api/create-order` | POST | `api_create_order` | Create Razorpay order. |
| `/api/verify-payment` | POST | `api_verify_payment` | Verify Razorpay payment and mark app order paid. |
| `/place-order/<int:product_id>` | POST | `place_order` | Direct checkout order creation fallback. |
| `/orders/<int:order_id>` | GET | `order_detail_redirect` | Redirect push notification link to order success. |
| `/order-success` | GET | `order_success` | Order confirmation page. |
| `/order/<int:product_id>` | POST | `create_order` | JSON/direct order creation fallback. |
| `/profile/addresses` | GET | `profile_addresses` | Saved address list. |
| `/profile/addresses/add` | GET, POST | `profile_address_add` | Add saved address. |
| `/profile/addresses/<int:addr_id>/edit` | GET, POST | `profile_address_edit` | Edit saved address. |
| `/profile/addresses/<int:addr_id>/delete` | POST | `profile_address_delete` | Delete saved address. |
| `/api/addresses` | POST | `api_address_create` | AJAX address creation. |
| `/profile/addresses/<int:addr_id>/set-default` | POST | `profile_address_set_default` | Set default saved address. |
| `/api/save-device-token` | POST | `api_save_device_token` | Save FCM device token. |
| `/api/remove-device-token` | POST | `api_remove_device_token` | Remove FCM device token. |
| `/api/firebase-config` | GET | `api_firebase_config` | Return Firebase web config. |
| `/profile/notifications` | GET | `profile_notifications` | Notification settings page. |
| `/my-commissions` | GET | `my_commissions` | Sales user commission list. |
| `/my-team` | GET | `my_team` | Upline, peers, and downline view. |
| `/onboard` | POST | `onboard` | Sales user onboarding under sponsor/referral ID. |
| `/api/team-stats` | GET | `team_stats` | Sales hierarchy stats JSON. |
| `/api/team-tree` | GET | `api_team_tree` | Sales downline tree JSON. |

### Admin Dashboard and User Management

| Route | Methods | Handler | Purpose |
|---|---:|---|---|
| `/admin` | GET | `admin_dashboard` | Admin dashboard alias. |
| `/admin-dashboard` | GET | `admin_dashboard` | Admin dashboard. |
| `/admin/create-first-sales-user` | GET, POST | `create_first_sales_user` | Super-admin first sales user bootstrap. |
| `/admin/users` | GET | `admin_users` | Super-admin user list. |
| `/admin-users` | GET | `admin_users` | User list alias. |
| `/admin/user/<int:user_id>` | GET, POST | `admin_user` | Super-admin user detail/update/reset password. |
| `/admin/user/create` | GET, POST | `admin_user_create` | Super-admin create user/admin. |
| `/admin-create-user` | GET, POST | `admin_user_create` | Create user alias. |
| `/admin/delete-user/<int:user_id>` | POST | `admin_delete_user` | Hard-delete safe sales user. |
| `/admin/user/<int:user_id>/delete` | POST | `admin_user_delete` | Delete admin or deactivate sales user. |
| `/admin/api/search-users` | GET | `admin_api_search_users` | Search sales users for admin tools. |
| `/admin/reassign-user` | GET, POST | `admin_reassign_user` | Move user under a new sponsor. |
| `/admin/search` | GET | `admin_search` | Find sales user by referral ID. |

### Admin Orders, Products, Commissions, System

| Route | Methods | Handler | Purpose |
|---|---:|---|---|
| `/admin/commissions` | GET | `admin_commissions` | Admin commission list and summary. |
| `/admin-commissions` | GET | `admin_commissions` | Commission alias. |
| `/admin/wallets` | GET | `admin_wallets` | Super-admin wallet balances. |
| `/admin-wallets` | GET | `admin_wallets` | Wallet alias. |
| `/admin/orders` | GET | `admin_orders` | Admin order list. |
| `/admin-orders` | GET | `admin_orders` | Orders alias. |
| `/admin/order/<int:order_id>/shipping-slip` | GET | `admin_order_shipping_slip` | Printable shipping slip. |
| `/admin/orders/<int:order_id>/mark-shipped` | POST | `admin_order_mark_shipped` | Mark shipped and notify. |
| `/admin/order/<int:order_id>/status` | POST | `admin_order_status` | Change order status. |
| `/admin-products` | GET | `admin_products` | Product/category admin. |
| `/admin-categories` | GET | `admin_products` | Category admin alias. |
| `/admin-products/category/add` | POST | `admin_category_add` | Add category. |
| `/admin-products/category/<int:cat_id>/edit` | POST | `admin_category_edit` | Edit category. |
| `/admin-products/category/<int:cat_id>/delete` | POST | `admin_category_delete` | Delete category. |
| `/admin-products/product/add` | GET, POST | `admin_product_add` | Add product. |
| `/admin-add-product` | GET, POST | `admin_product_add` | Add product alias. |
| `/admin-products/product/<int:prod_id>/edit` | GET, POST | `admin_product_edit` | Edit product. |
| `/admin-products/product/<int:prod_id>/delete` | POST | `admin_product_delete` | Delete product. |
| `/admin/tree-health` | GET | `admin_tree_health` | Super-admin tree integrity page. |
| `/admin/tree-health/fix` | POST | `admin_tree_health_fix` | Apply tree integrity fix. |
| `/admin/recalculate-commission` | GET, POST | `admin_recalculate_commission` | Super-admin commission recalculation. |
| `/admin/activity-logs` | GET | `admin_activity_logs` | Super-admin activity logs. |
| `/admin-activity-logs` | GET | `admin_activity_logs` | Activity logs alias. |
| `/admin-sales-report` | GET | `admin_report_placeholder` | Placeholder report route. |
| `/admin-commission-report` | GET | `admin_report_placeholder` | Placeholder report route. |
| `/admin/notifications` | GET, POST | `admin_notifications` | Admin notification center. |

## Templates

### Public and Shared Templates

- `templates/base.html`: logged-in app layout with sidebar/topbar.
- `templates/base_public.html`: public site layout.
- `templates/index.html`: public homepage.
- `templates/catalog.html`: public catalog.
- `templates/about.html`: about page.
- `templates/director_message.html`: director message page.
- `templates/contact.html`: contact form.
- `templates/faq.html`: FAQ page.
- `templates/login.html`: login page.
- `templates/register.html`: public referral registration.
- `templates/setup.html`: first admin setup.
- `templates/offline.html`: PWA offline fallback.
- `templates/service_worker.js`: dynamic Firebase-enabled service worker template.

### Sales User Templates

- `templates/dashboard.html`: sales dashboard.
- `templates/products.html`: logged-in products.
- `templates/checkout.html`: checkout and Razorpay launch page.
- `templates/order_success.html`: order confirmation.
- `templates/my_team.html`: upline, peers, downline, onboarding UI.
- `templates/my_commissions.html`: commission list.
- `templates/profile_addresses.html`: saved address management.
- `templates/address_form.html`: add/edit address form.
- `templates/profile_notifications.html`: push notification settings.

### Admin Templates

- `templates/admin/admin_dashboard.html`: admin dashboard.
- `templates/admin/super_admin_dashboard.html`: super-admin dashboard.
- `templates/admin/dashboard.html`: legacy/admin dashboard template.
- `templates/admin/users.html`: user list.
- `templates/admin/user_detail.html`: user detail/update/reset.
- `templates/admin/user_create.html`: user creation form.
- `templates/admin/create_first_sales.html`: first sales user bootstrap.
- `templates/admin/commissions.html`: commission admin.
- `templates/admin/wallets.html`: wallet balances.
- `templates/admin/orders.html`: order admin.
- `templates/admin/shipping_slip.html`: printable shipping slip.
- `templates/admin/products.html`: product/category list.
- `templates/admin/product_form.html`: product add/edit form.
- `templates/admin/tree_health.html`: tree integrity UI.
- `templates/admin/recalculate_commission.html`: commission recalculation UI.
- `templates/admin/reassign_user.html`: user reassignment UI.
- `templates/admin/notifications.html`: notification center.
- `templates/admin/activity_logs.html`: activity log table.

### Email Templates

- `templates/email_base_order.html`: shared order-email base.
- `templates/email_welcome.html`: welcome email.
- `templates/email_credentials.html`: credentials email.
- `templates/email_notification.html`: admin notification email.
- `templates/email_contact_form.html`: contact form email template.
- `templates/email_order_notification.html`: admin new-order email.
- `templates/email_order_confirmation_buyer.html`: buyer order confirmation.
- `templates/email_order_shipped_buyer.html`: buyer shipped email.
- `templates/email_order_shipped_admin.html`: admin shipped email.
- `templates/email_test.html`: email test page.

## Integrations

### Razorpay

Backend:

- Configured with `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`.
- `api_create_order()` creates Razorpay orders.
- `api_verify_payment()` verifies signature and marks app order as paid.
- Helpers live in `integrations/razorpay_checkout.py`.

Frontend:

- `templates/checkout.html` defines `window.CHECKOUT_CONFIG`.
- `static/js/razorpay-checkout.js` calls backend checkout APIs and opens Razorpay modal.
- Razorpay script is loaded from `https://checkout.razorpay.com/v1/checkout.js`.

### Firebase Cloud Messaging

Backend:

- Configured with `FIREBASE_API_KEY`, `FIREBASE_PROJECT_ID`, `FIREBASE_APP_ID`, `FIREBASE_MESSAGING_SENDER_ID`, `FIREBASE_VAPID_KEY`, and `FIREBASE_SERVICE_ACCOUNT_PATH`.
- `get_firebase_app()` lazy-loads Firebase Admin SDK.
- `send_push_notification()` sends multicast messages.
- `DeviceToken` stores browser/device tokens.

Frontend:

- `/api/firebase-config` exposes web config.
- `static/js/firebase-notifications.js` manages permissions and FCM token registration.
- `/service-worker.js` serves either static service worker or Firebase-enabled service worker.

### Resend Email

- `integrations/resend_email.py` posts to `https://api.resend.com/emails`.
- Uses `RESEND_API_KEY`.
- Used by welcome, new-order, buyer-confirmation, and buyer-shipped email helpers.

### SMTP Email

- Configured with `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, and `MAIL_FROM`.
- Used by credentials email, admin shipped email, notification-center email, contact form email, and email-test page.

## Major Workflow Call Graphs

### App Startup

```text
import app.py
  -> load_dotenv()
  -> Flask(...)
  -> db = SQLAlchemy(app)
  -> define helpers/models/routes
  -> with app.app_context()
     -> migrate_db()
        -> db.create_all()
        -> ALTER TABLE checks/backfills
        -> ensure super_admin user
        -> ensure categories
        -> backfill orders/wallets/referral IDs
     -> if Product.query.count() == 0
        -> seed sample products
```

### Login

```text
POST /login
  -> login()
     -> find User by email or username
     -> user.check_password(password)
     -> user.is_user_active
     -> if admin submit
        -> user.is_admin_role
        -> set session
        -> redirect admin_dashboard
     -> else
        -> set session
        -> admin users redirect admin_dashboard
        -> sales users redirect dashboard
```

### Public Registration

```text
POST /register
  -> register()
     -> resolve referral_id to parent User
     -> validate unique username/email
     -> generate_referral_id()
     -> create User(parent_id=parent.id, user_level=1, user_role='user')
     -> db.session.commit()
     -> get_or_create_wallet(new_user.id)
     -> send_welcome_email(new_user)
        -> render_template(email_welcome.html)
        -> integrations.resend_email.send_email()
     -> walk parent chain
        -> check_and_promote_user(current.id)
     -> redirect login
```

### Sales Onboarding

```text
POST /onboard
  -> onboard()
     -> require logged-in sales user
     -> optional referral_id overrides parent_user
     -> validate unique username/email
     -> generate_referral_id()
     -> create child User(parent_id=parent_user.id)
     -> db.session.commit()
     -> get_or_create_wallet(new_user.id)
     -> send_welcome_email(new_user)
     -> walk sponsor chain
        -> check_and_promote_user(current.id)
           -> count_direct_at_level(user, user.user_level)
           -> create PromotionHistory when threshold reached
     -> return JSON success/promotion status
```

### Razorpay Checkout

```text
GET /checkout
  -> checkout()
     -> validate logged-in non-admin user
     -> load Product
     -> load saved Address records
     -> render templates/checkout.html
        -> static/js/razorpay-checkout.js

User clicks Pay Now
  -> startRazorpayCheckout(form)
     -> POST /api/checkout/prepare-pending
        -> checkout_prepare_pending()
           -> _checkout_user_or_error()
           -> load Product
           -> _parse_checkout_shipping()
           -> create Order(payment_status='Pending')
           -> store pending_checkout_form in session
           -> return app_order_id, amount_paise, receipt
     -> POST /api/create-order
        -> api_create_order()
           -> validate Razorpay config
           -> validate app order ownership/status
           -> get_razorpay_client()
           -> create_razorpay_order()
           -> save order.razorpay_order_id
           -> return Razorpay order data
     -> open Razorpay modal
     -> handler(response)
        -> POST /api/verify-payment
           -> api_verify_payment()
              -> verify_payment_signature()
              -> validate app order ownership/status
              -> mark order Paid
              -> decrement stock
              -> distribute_commission(order)
              -> send_order_notification(order)
              -> send_order_confirmation_buyer(order)
              -> send_push_notification(order.user_id, ...)
              -> _maybe_save_checkout_address()
              -> return success
     -> redirect /order-success?order_id=...
```

### Direct/Fallback Order Creation

```text
POST /place-order/<product_id>
  -> place_order()
     -> validate sales user and active account
     -> load Product
     -> parse selected/manual shipping address
     -> create Order(payment_status='Paid')
     -> decrement stock
     -> optionally save Address
     -> distribute_commission(order)
     -> send_order_notification(order)
     -> send_order_confirmation_buyer(order)
     -> send_push_notification(order.user_id, ...)
     -> redirect order_success

POST /order/<product_id>
  -> create_order()
     -> validate sales user and active account
     -> load Product
     -> create Order(payment_status='Paid')
     -> decrement stock
     -> distribute_commission(order)
     -> send_order_notification(order)
     -> send_order_confirmation_buyer(order)
     -> send_push_notification(order.user_id, ...)
     -> return JSON
```

### Commission Distribution

```text
distribute_commission(order)
  -> require order.payment_status == 'Paid'
  -> skip if order.commission_generated
  -> buyer = order.user
  -> require buyer.is_sales_user and buyer.is_user_active
  -> buyer.get_commission_upline_chain(10)
     -> walk parent chain
     -> stop at admin/super_admin
     -> skip inactive uplines
  -> for each upline in first 10
     -> percentage = hierarchy.COMMISSION_BY_LEVEL[level]
     -> create Commission
     -> get_or_create_wallet(upline_user.id)
     -> increment wallet.total_earnings
     -> increment wallet.available_balance
  -> order.commission_generated = True
  -> db.session.commit()
```

### Order Shipping

```text
POST /admin/orders/<order_id>/mark-shipped
  -> admin_order_mark_shipped()
     -> require_admin
     -> load Order
     -> set status='Shipped'
     -> set shipped_at
     -> db.session.commit()
     -> log_activity()
     -> send_order_shipped_buyer(order)
     -> send_order_shipped_admin(order)
     -> send_push_notification(order.user_id, ...)
     -> return JSON or redirect

POST /admin/order/<order_id>/status
  -> admin_order_status()
     -> require_admin
     -> load Order
     -> if Cancelled and commission_generated
        -> reverse_commission(order)
     -> update status
     -> if status Shipped and no shipped_at
        -> send shipped notifications
     -> db.session.commit()
     -> log_activity()
```

### Address Management

```text
GET /profile/addresses
  -> profile_addresses()
     -> load current user's addresses
     -> render profile_addresses.html

POST /profile/addresses/add
  -> profile_address_add()
     -> _validate_address_form()
     -> create Address
     -> first address becomes default

POST /api/addresses
  -> api_address_create()
     -> _validate_address_form()
     -> create Address
     -> return address JSON for checkout modal

POST /profile/addresses/<addr_id>/set-default
  -> profile_address_set_default()
     -> set selected address default
     -> clear default on others
```

### Firebase Push Token Registration

```text
User opens notification settings/dashboard
  -> static/js/firebase-notifications.js
     -> fetch /api/firebase-config
     -> Notification.requestPermission()
     -> navigator.serviceWorker.getRegistration('/') or register('/service-worker.js')
     -> firebase.messaging().getToken(...)
     -> POST /api/save-device-token
        -> api_save_device_token()
           -> create DeviceToken unless duplicate

Disable notifications
  -> POST /api/remove-device-token
     -> api_remove_device_token()
        -> delete one token or all tokens for user
```

### Admin Notification Center

```text
GET /admin/notifications
  -> admin_notifications()
     -> render admin/notifications.html

POST /admin/notifications
  -> admin_notifications()
     -> _admin_notifications_post()
        -> validate title/message/audience/methods
        -> _get_notification_recipients()
        -> if push selected
           -> send_push_notification(user_ids, ...)
        -> if email selected
           -> send_notification_email(email, ...)
        -> create Notification log
        -> log_activity()
        -> return JSON or redirect
```

### Tree Health Fix

```text
GET /admin/tree-health
  -> admin_tree_health()
     -> scan_tree_integrity()
        -> detect orphan parent_id
        -> detect circular references
        -> detect admin/super_admin in referral tree
        -> detect duplicate referral_id
     -> render admin/tree_health.html

POST /admin/tree-health/fix
  -> admin_tree_health_fix()
     -> apply requested fix
        -> parent_id = NULL for orphan/circular/admin_in_tree
        -> generate_referral_id() for duplicate_ref
     -> log_activity()
     -> return JSON
```

### User Reassignment

```text
POST /admin/reassign-user
  -> admin_reassign_user()
     -> require_admin
     -> load user and new_parent
     -> reject missing users
     -> reject root user
     -> reject self-assignment
     -> reject admin/super_admin sponsor
     -> reject moving user under own descendant
        -> user.get_all_descendants()
     -> update user.parent_id
     -> db.session.commit()
     -> log_activity()
     -> return JSON
```

### Commission Recalculation

```text
POST /admin/recalculate-commission
  -> admin_recalculate_commission()
     -> require_super_admin
     -> resolve orders by mode
        -> order
        -> user
        -> date_range
     -> filter Paid orders
     -> recalculate_commissions_for_orders(paid_orders)
        -> _clear_order_commissions(order)
        -> distribute_commission(order)
     -> log_activity()
     -> return JSON
```

## Maintenance Notes

- `app.py` is the central maintenance bottleneck because it owns configuration, models, routes, migrations, business logic, and integrations.
- `migrate_db()` performs manual SQLite migrations and data mutation at import time.
- Email delivery is split between Resend and SMTP.
- Order creation exists in multiple paths: Razorpay checkout and direct paid-order fallbacks.
- There are two SQLite database files in the repository tree: `instance/sales_team.db` and `sales_team.db`.
- Several templates include substantial inline JavaScript, especially checkout and admin notifications.
