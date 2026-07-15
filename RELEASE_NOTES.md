# Abound Next-Gen E-Hub
## Release Notes

---

## Version 1.1.0 – Retail Customer & Rewards System

### New Features

- **Retail Customer Purchase Flow**: Complete dedicated retail checkout experience for non-sales users
- **Direct Purchase Without Referral ID**: Retail customers can browse and buy without a referral ID
- **Auto Customer Account Creation**: Automatic account creation for new retail customers using email/phone matching
- **Assigned Sales Member**: Sales member assignment for retail customers (tracks relationships)
- **Savings Points Engine**: Points earned per purchase (configurable rate)
- **Customer Dashboard**: Dedicated dashboard for retail customers with savings points, order history, and assigned member
- **My Customers Section**: Sales members can view their assigned retail customers with purchase history
- **Admin Customer Rewards**: Admin interface to manage customer reward eligibility and redemptions
- **Savings Redemption**: Record and track savings point redemptions for gifts/rewards
- **Reward Eligibility Workflow**: Automatic eligibility status tracking when customers reach threshold
- **One-Time Reward Notification Emails**: Admin notification only once when customer first reaches reward threshold

### Improvements

- **Separation of Retail Customers from Sales Members**: Clear role distinction (`user_role='customer'` vs `'user'`)
- **Separate Rewards Engine from Commission Engine**: Independent savings/rewards system that doesn't interfere with existing commissions
- **Configurable Savings Point Rate**: `SAVINGS_POINT_RATE` constant for easy adjustment
- **Configurable Reward Threshold**: `REWARD_THRESHOLD` constant to set eligibility points
- **Improved Database Migration**: Safely adds new columns and tables without modifying existing data
- **Existing Commission System Preserved**: No changes to existing referral hierarchy or commission logic

### Infrastructure

- **GitHub Integration**: Project connected to GitHub repository
- **Render Deployment**: Deployed on Render platform
- **Custom Domain**: Configured custom domain
- **HTTPS**: Full HTTPS enabled
- **Razorpay Integration**: Payment gateway integration for secure transactions
- **Firebase Push Notifications**: Push notifications for order updates and announcements
- **Resend Email Migration**: Email delivery migrated to Resend API
- **PROJECT_MAP.md**: Comprehensive project documentation
- **Codex/TRAE Development Workflow**: Professional development workflow established

### Database Changes

#### New Models
- **SavingsAccount**: Tracks customer savings points and reward status
  - `customer_id`: Foreign key to User
  - `current_points`: Current available points
  - `lifetime_points`: Total points earned
  - `eligible_since`: Date/time of reward eligibility
  - `reward_status`: Current reward status (NORMAL, ELIGIBLE, PENDING, DELIVERED)
  - `eligibility_email_sent`: Flag to prevent duplicate eligibility emails
- **SavingsRedemption**: Tracks savings point redemptions
  - `customer_id`: Foreign key to User
  - `points_redeemed`: Number of points redeemed
  - `reward_name`: Name of reward/gift
  - `admin_id`: Foreign key to User (admin who processed redemption)
  - `remarks`: Optional notes

#### New User Fields
- `assigned_member_id`: Foreign key to User (sales member assigned to customer)

#### Migration Additions
- `eligibility_email_sent`: Added to SavingsAccount to track one-time eligibility notifications

### Email System

All email delivery now uses Resend for the following:
- Welcome Emails
- Order Confirmation
- Order Notifications
- Shipping Notifications
- Notification Centre
- Contact Form

### Security

- **Secure Customer Account Generation**: New retail customer accounts created with secure password hashing
- **Existing Authentication Preserved**: Sales users continue using existing authentication flow
- **Existing Payment Verification Preserved**: Razorpay signature verification unchanged

### Known Limitations

- Product Discount Engine pending
- Google Play packaging pending
- PostgreSQL migration planned
- Customer analytics pending

### Testing Completed

- Existing Sales Flow (unchanged)
- Retail Checkout (new)
- Customer Login
- Rewards Engine
- Emails
- Database Migration
- Admin Pages

---

## Version 1.2.0 – Product Discount Engine

### Planned Features

- MRP (Maximum Retail Price) field
- Selling Price field
- Discount Percentage calculation
- Strikethrough Pricing display
- Discount badges on product cards
- Savings display for customers
- Admin discount management interface
