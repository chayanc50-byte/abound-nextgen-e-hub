# Abound Next-Gen E-Hub — Video Walkthrough Script

A production-ready script for recording a professional walkthrough video highlighting **technical**, **functional**, and **aesthetic** aspects of the website.

---

## Recording Setup Tips

- **Duration:** 8–12 minutes recommended  
- **Tools:** OBS Studio, Loom, QuickTime (Mac), or Windows Game Bar  
- **Resolution:** 1080p  
- **Browser:** Use Incognito/Private mode for clean sessions  
- **Pace:** Slow, deliberate cursor movements; pause 2–3 seconds on key elements  

---

## SCRIPT (with timestamps & talking points)

### INTRO (0:00 – 0:45)

**[Screen: Homepage hero]**

> "Welcome to the Abound Next-Gen E-Hub walkthrough. This video covers the technical architecture, core features, and design of this e-commerce and multi-level business platform."

**Highlight:**
- Orange gradient hero with overlay and clear value proposition
- Clean typography (Poppins), responsive layout
- Strong CTAs: "Join Now" and "Explore Products"

---

### 1. PUBLIC PAGES & AESTHETICS (0:45 – 2:30)

#### Navigation & Header

**[Scroll to show header]**

> "The header uses a responsive layout: full navigation on desktop, hamburger menu on mobile."

**Show:**
- Logo area, nav links (Home, Products, Categories, About, Contact, FAQ, Join Us)
- Login and Register buttons, cart icon
- Mobile: open hamburger and sidebar

#### Homepage Sections

**[Scroll down homepage]**

> "The homepage uses clear sections with visual hierarchy."

**Highlight:**
1. **Product categories** — 6 icon cards (Household, Grocery, Cosmetics, Personal Care, Kitchen, Daily Needs)
2. **Popular products** — Product cards with image placeholder, price in ₹
3. **Feature cards** — Trusted Products, Business Opportunity, Growing Network, Reliable Support
4. **Business CTA** — "Build Your Own Business" with prominent "Become a Partner" button
5. **Final CTA** — "Start Your Journey Today"

**Technical notes to mention:**
- CSS Grid for layouts (`categories-grid`, `products-grid`, `features-grid`)
- Section backgrounds alternate for clear separation
- All CTAs lead to register, catalog, or other key flows

---

### 2. PRODUCT CATALOG (2:30 – 3:15)

**[Go to /catalog]**

> "The product catalog lists all available products with filtering by category."

**Show:**
- Category filter (dropdown or tabs)
- Product grid with image, name, price
- Click product → redirects to login (if not logged in)

**Technical:**
- Flask + Jinja2 templates
- SQLAlchemy models: Product, Category
- Catalog route uses category filter

---

### 3. ABOUT & DIRECTOR MESSAGE (3:15 – 4:00)

**[Go to /about]**

> "The About page introduces the company and leadership."

**Show:**
- About content, company info
- "Message from our Director" card → link to director message page

**[Go to /about/director-message]**

> "The Director Message page shows a more personal introduction with a director profile image, message, and signature."

**Aesthetic notes:**
- Hero layout consistent with other pages
- Card-based layout, optional image placeholders

---

### 4. CONTACT — SUPPORT CENTER (4:00 – 4:45)

**[Go to /contact]**

> "The Contact page is built as a support center."

**Highlight in order:**
1. **Hero** — "Contact Us"
2. **Contact info card** — Phone, Email, Address, Facebook
3. **Support options** — 3 cards:
   - Call (tap-to-call)
   - WhatsApp (external link)
   - Email (mailto)
4. **Office address** — Full address plus Google Maps embed
5. **Contact form** — Name, Email, Subject, Message, Send button
6. **Quick links** — Home, About, FAQ, Login

**Technical:**
- POST form sends data to Flask backend
- Email sent via SMTP (configurable via env vars)
- Responsive grid for support cards

---

### 5. FAQ (4:45 – 5:00)

**[Go to /faq]**

> "The FAQ page uses an accordion layout for common questions."

**Show:**
- Expand/collapse interaction on one or two items

---

### 6. REGISTRATION FLOW (5:00 – 6:15)

**[Go to /register]**

> "Registration uses an email and referral-code flow."

**Show:**
1. Enter email
2. Enter referral code (or skip if allowed)
3. Submit → redirect to Setup page

**[Setup page]**

> "New users complete their profile: name, username, password."

**Show:**
- Setup form fields
- Submit → welcome email (if configured) + redirect to dashboard or login

**Technical:**
- Unique referral IDs (ABN + 5 chars)
- Parent–child relationships in the user hierarchy
- Email integration for welcome and credentials

---

### 7. LOGIN & USER DASHBOARD (6:15 – 7:30)

**[Login with a sales user]**

> "After login, sales users see their dashboard."

**Show:**
- Dashboard cards (orders, team count, commissions, etc.)
- Sidebar: Dashboard, Products, My Orders, My Team, My Commissions, Profile
- Header with user name and logout

**Products page:**
- Browse products
- Place order (quantity, shipping address)
- Order confirmation and flash message

**My Team:**
- Hierarchical team view (direct referrals)
- Tree or list showing downline

**My Commissions:**
- Commission records from referred orders
- Amounts and status

**Technical:**
- Role-based access (user, admin, super_admin)
- Multi-level referral structure
- Commission distribution on paid orders

---

### 8. ADMIN PANEL (7:30 – 9:30)

**[Logout and login as admin]**

> "Administrators have access to the admin panel."

**Show in order:**

1. **Admin Dashboard**
   - Overview stats, quick actions

2. **Users**
   - List of users
   - Create user (manual or invite)
   - Edit user (level, status, roles)
   - Delete user (with confirmation)

3. **Products & Categories**
   - Category CRUD
   - Product CRUD (name, price, image, category, stock)
   - Image upload

4. **Orders**
   - Order list with status
   - Update order status (Pending → Processing → Shipped → Delivered)
   - Payment status and commission handling

5. **Commissions**
   - Commission list per user
   - Links to orders

6. **Wallets**
   - Earnings, available balance, withdrawn

7. **Activity Logs**
   - Admin actions with timestamps
   - Audit trail

**Technical:**
- `require_admin` and `require_super_admin` decorators
- Super Admin for sensitive operations
- SQLAlchemy models: User, Product, Order, Commission, Wallet, ActivityLog

---

### 9. TECHNICAL SUMMARY (9:30 – 10:15)

**[Screen: Optional – code or architecture slide]**

> "A quick technical overview:"

**Mention:**
- **Backend:** Flask, Python
- **Database:** SQLite via SQLAlchemy
- **Auth:** Werkzeug password hashing, session-based auth
- **Email:** SMTP for welcome, order notifications, contact form
- **Frontend:** Jinja2 templates, vanilla CSS (responsive, flexbox, grid)
- **Features:** Multi-level hierarchy, referral IDs, commission distribution, role-based access

---

### 10. RESPONSIVE & CLOSING (10:15 – 10:45)

**[Resize browser or use device toolbar]**

> "The site is responsive: the header switches to a hamburger menu, grids reflow, and touch targets are sized for mobile."

**Show:**
- Mobile view of homepage or contact page
- Hamburger menu open
- Support/CTA buttons on mobile

**Closing:**

> "That completes the Abound Next-Gen E-Hub walkthrough — covering public pages, user flows, admin tools, and responsive design. Thank you for watching."

---

## Quick Reference: Key URLs

| Page         | URL                   |
|-------------|------------------------|
| Home        | `/`                    |
| Catalog     | `/catalog`             |
| About       | `/about`              |
| Director    | `/about/director-message` |
| Contact     | `/contact`            |
| FAQ         | `/faq`                |
| Register    | `/register`           |
| Login       | `/login`               |
| Dashboard   | `/dashboard`          |
| Products    | `/products`           |
| My Team     | `/my-team`            |
| Commissions | `/my-commissions`     |
| Admin       | `/admin` or `/admin-dashboard` |
| Admin Users | `/admin/users`        |
| Admin Products | `/admin-products`   |
| Admin Orders| `/admin/orders`       |

---

## Suggested Video Title & Description

**Title:** Abound Next-Gen E-Hub — Full Website Walkthrough

**Description (short):**
> Walkthrough of Abound Next-Gen E-Hub: e-commerce platform with multi-level referral system, admin panel, support center, and responsive design. Covers technical architecture, main features, and UI/UX.

---

*Script prepared for recording. Adjust timing and tone as needed.*
