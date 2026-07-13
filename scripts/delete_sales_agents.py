#!/usr/bin/env python3
"""
One-off script: Delete all sales agents except Baidya001.
Keeps admins/super_admins intact. Resets Baidya001 to root (no parent).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from app import User, Order, Commission, Wallet, PromotionHistory

def main():
    baidya = User.query.filter_by(username='Baidya001').first()
    if not baidya:
        print("ERROR: User 'Baidya001' not found in database. Aborting.")
        sys.exit(1)

    if not baidya.is_sales_user:
        print("ERROR: 'Baidya001' is not a sales user (role={}). Aborting.".format(
            getattr(baidya, 'user_role', None)))
        sys.exit(1)

    to_delete = User.query.filter(
        User.user_role == 'user',
        User.id != baidya.id
    ).all()

    print(f"Keeping: Baidya001 (id={baidya.id})")
    print(f"Deleting {len(to_delete)} sales agent(s): {[u.username for u in to_delete]}")

    if not to_delete:
        print("No sales agents to delete.")
        return

    delete_ids = [u.id for u in to_delete]
    order_ids_from_deleted = [o.id for o in Order.query.filter(Order.user_id.in_(delete_ids)).all()]

    Commission.query.filter(
        db.or_(
            Commission.user_id.in_(delete_ids),
            Commission.order_id.in_(order_ids_from_deleted)
        )
    ).delete(synchronize_session=False)
    Order.query.filter(Order.user_id.in_(delete_ids)).delete(synchronize_session=False)
    Wallet.query.filter(Wallet.user_id.in_(delete_ids)).delete(synchronize_session=False)
    PromotionHistory.query.filter(PromotionHistory.user_id.in_(delete_ids)).delete(synchronize_session=False)

    for u in to_delete:
        u.parent_id = None
    db.session.flush()
    baidya.parent_id = None
    db.session.flush()

    for u in to_delete:
        db.session.delete(u)

    db.session.commit()
    print("Done. All sales agents deleted except Baidya001. Baidya001 set as root.")

if __name__ == '__main__':
    with app.app_context():
        main()
