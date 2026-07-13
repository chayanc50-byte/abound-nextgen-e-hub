#!/usr/bin/env python3
"""Clear all commissions and orders from the database. Reset wallet balances to zero."""
import os
import sys

# Add parent directory so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db, Commission, Order, Wallet

def clear_commissions_and_orders():
    with app.app_context():
        comm_count = Commission.query.count()
        order_count = Order.query.count()
        
        # Delete commissions first (they reference orders)
        Commission.query.delete()
        
        # Delete all orders (purchases)
        Order.query.delete()
        
        # Reset all wallet balances to zero
        for w in Wallet.query.all():
            w.total_earnings = 0
            w.available_balance = 0
            w.withdrawn_balance = 0
        
        db.session.commit()
        
        print(f"Cleared {comm_count} commissions and {order_count} orders.")
        print("Reset all wallet balances to zero.")
        print("Done.")

if __name__ == '__main__':
    clear_commissions_and_orders()
